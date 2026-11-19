"""Bloque 29: pruebas negativas del validador, balance y evaluación offline.

Los ejemplos rotos se generan aquí (en memoria o en tmp_path); nunca se agregan al dataset final.
"""
from __future__ import annotations

import json

import pytest

from src.personalizacion.balance import chequear_balance, formatear_balance
from src.personalizacion.dataset import RUTA_VALIDACION, cargar_ejemplos
from src.personalizacion.evaluacion import evaluar_respuestas, respuestas_de_referencia
from src.personalizacion.validacion import (
    ADVERTENCIA, ERROR, advertencias, errores, solapamiento, validar_dataset, validar_salida,
)


def ej(entrada, categoria="red", accion="reintentar con backoff exponencial", **extra):
    return {"entrada": entrada, "salida": json.dumps({"categoria": categoria, "accion_sugerida": accion, **extra},
                                                     ensure_ascii=False)}


def codigos(problemas, nivel=None):
    return [p.codigo for p in problemas if nivel is None or p.nivel == nivel]


# --- validar_salida -----------------------------------------------------------------------

@pytest.mark.parametrize("salida, codigo", [
    ("", "salida_vacia"),
    ("   ", "salida_vacia"),
    ('{"categoria": "red", "accion_sugerida": "x"', "json_malformado"),
    ("['red']", "json_malformado"),
    ('["red"]', "json_no_objeto"),
    ('{"categoria": "red"}', "clave_faltante"),
    ('{"categoria": "red", "accion_sugerida": "reintentar", "extra": 1}', "clave_inesperada"),
    ('{"categoria": "disco", "accion_sugerida": "liberar espacio"}', "categoria_desconocida"),
    ('{"categoria": 3, "accion_sugerida": "x"}', "tipo_categoria"),
    ('{"categoria": "red", "accion_sugerida": ""}', "accion_vacia"),
    ('{"categoria": "red", "accion_sugerida": ["reintentar"]}', "tipo_accion"),
    ('{"categoria": "autenticacion", "accion_sugerida": "reintentar con backoff"}', "contradiccion"),
    ('{"categoria": "red", "accion_sugerida": "reconstruir el índice"}', "contradiccion"),
    ('{"categoria": "entorno", "accion_sugerida": "esperar a que se renueve la cuota"}', "contradiccion"),
    (None, "tipo_salida"),
])
def test_validar_salida_detecta(salida, codigo):
    _, fallos = validar_salida(salida)
    assert codigo in [c for c, _ in fallos]


def test_no_reintentar_negado_no_es_contradiccion():
    _, fallos = validar_salida('{"categoria": "autenticacion", "accion_sugerida": "revisar API_KEY; no reintentar"}')
    assert fallos == []


def test_varios_fallos_en_una_misma_salida():
    _, fallos = validar_salida('{"categoria": "disco", "otra": 1}')
    assert {"clave_faltante", "clave_inesperada", "categoria_desconocida"} <= {c for c, _ in fallos}


# --- validar_dataset: dataset corrupto ----------------------------------------------------

def dataset_corrupto():
    return [
        ej("Timeout al conectar con Gemini"),                                   # 0 válido
        {"entrada": "", "salida": ej("x")["salida"]},                          # 1 entrada vacía
        {"entrada": "Error 401", "salida": ""},                                # 2 salida vacía
        {"entrada": "Error 403", "salida": "{no es json"},                      # 3 JSON malformado
        {"entrada": "Error 429", "salida": '{"categoria": "cuota"}'},           # 4 clave faltante
        ej("Error 500 del servidor", extra="sobra"),                            # 5 clave inesperada
        ej("Disco lleno", categoria="disco", accion="liberar espacio"),         # 6 categoría desconocida
        ej("API key not valid", categoria="autenticacion", accion="   "),       # 7 acción vacía
        {"entrada": 123, "salida": ej("y")["salida"]},                          # 8 tipo de entrada
        ej("API key not valid 2", categoria="autenticacion", accion="reintentar con backoff"),  # 9 contradicción
        ej("Timeout al conectar con Gemini"),                                   # 10 registro idéntico a 0
        ej("timeout al conectar con  gemini", categoria="cuota", accion="esperar"),  # 11 entrada duplicada, otra salida
        "no soy un objeto",                                                     # 12 tipo de ejemplo
        {"entrada": "sin salida"},                                              # 13 falta salida
        {"entrada": "Fallo de red", "salida": ej("z")["salida"], "id": 7},      # 14 clave de ejemplo inesperada
        ej("Timeout al conectar con Gemini!"),                                  # 15 casi igual a 0 (advertencia)
    ]


def test_validador_reporta_todos_los_errores_en_una_pasada():
    problemas = validar_dataset(dataset_corrupto())
    esperados = {
        "entrada_vacia", "salida_vacia", "json_malformado", "clave_faltante", "clave_inesperada",
        "categoria_desconocida", "accion_vacia", "tipo_entrada", "contradiccion", "registro_identico",
        "entrada_duplicada", "tipo_ejemplo", "clave_ejemplo_faltante", "clave_ejemplo_inesperada",
    }
    assert esperados <= set(codigos(problemas, ERROR))
    assert "entradas_muy_parecidas" in codigos(problemas, ADVERTENCIA)
    # Cada error apunta al ejemplo roto correcto.
    por_codigo = {p.codigo: p.indices for p in errores(problemas)}
    assert por_codigo["json_malformado"] == (3,)
    assert por_codigo["registro_identico"] == (0, 10)
    assert por_codigo["entrada_duplicada"] == (0, 11)


def test_entrada_duplicada_con_salida_contradictoria():
    problemas = validar_dataset([ej("Error X", "red"), ej("error  x", "cuota", "esperar y reducir el ritmo")])
    [dup] = [p for p in problemas if p.codigo == "entrada_duplicada"]
    assert "DISTINTAS" in dup.mensaje


def test_dataset_no_lista_o_vacio():
    assert codigos(validar_dataset({"a": 1})) == ["dataset_no_lista"]
    assert codigos(validar_dataset([])) == ["dataset_vacio"]


def test_dataset_corrupto_en_archivo_temporal(tmp_path):
    ruta = tmp_path / "roto.json"
    ruta.write_text(json.dumps(dataset_corrupto(), ensure_ascii=False), encoding="utf-8")
    assert len(errores(validar_dataset(cargar_ejemplos(ruta)))) >= 14


def test_cli_devuelve_1_con_dataset_corrupto(tmp_path, capsys):
    from src.dataset_tuning import main

    roto = tmp_path / "roto.json"
    roto.write_text(json.dumps(dataset_corrupto(), ensure_ascii=False), encoding="utf-8")
    assert main(["--entrenamiento", str(roto)]) == 1
    salida = capsys.readouterr().out
    assert "json_malformado" in salida and "no se construyen objetos de tuning" in salida


def test_accion_poco_relacionada_es_advertencia():
    problemas = validar_dataset([ej("Fallo extraño", "red", "llamar al equipo")])
    assert codigos(problemas) == ["accion_poco_relacionada"]
    assert advertencias(problemas) and not errores(problemas)


def test_solapamiento_detecta_fuga_y_parecidos():
    entrenamiento = [ej("Timeout al conectar con Gemini"), ej("ModuleNotFoundError: No module named 'chromadb'",
                                                              "entorno", "instalar dependencias")]
    validacion = [ej("timeout al conectar con gemini"), ej("ModuleNotFoundError: No module named 'chromadbx'",
                                                           "entorno", "instalar dependencias")]
    problemas = solapamiento(entrenamiento, validacion)
    assert "fuga_validacion" in codigos(problemas, ERROR)
    assert "validacion_parecida_a_entrenamiento" in codigos(problemas, ADVERTENCIA)


# --- Balance --------------------------------------------------------------------------------

def test_balance_con_counter():
    datos = [ej(f"r{i}") for i in range(4)] + [ej(f"c{i}", "cuota", "esperar") for i in range(2)] + \
            [ej("a", "autenticacion", "revisar clave"), {"entrada": "x", "salida": "roto"}]
    resumen = chequear_balance(datos)
    assert resumen.total == 8
    assert resumen.conteos["red"] == 4 and resumen.conteos["cuota"] == 2 and resumen.conteos["entorno"] == 0
    assert resumen.porcentajes["red"] == pytest.approx(50.0)
    assert resumen.mayoritarias == ["red"]
    assert set(resumen.minoritarias) == {"entorno", "consistencia_indice"}
    assert resumen.relacion_max_min is None  # Hay categorías con 0 ejemplos.
    assert resumen.sin_categoria_valida == 1
    assert "no calculable" in formatear_balance(resumen)


def test_balance_relacion_y_umbral():
    datos = [ej(f"r{i}") for i in range(3)] + [ej(f"{c}{i}", c, "x") for c in
                                                ("autenticacion", "cuota", "entorno", "consistencia_indice")
                                                for i in range(2)]
    resumen = chequear_balance(datos)
    assert resumen.relacion_max_min == pytest.approx(1.5)
    assert resumen.dentro_de_umbral(1.5) and not resumen.dentro_de_umbral(1.4)


def test_sin_errores_no_implica_balanceado():
    datos = [ej(f"Timeout {i}") for i in range(10)]
    assert errores(validar_dataset(datos)) == []
    assert chequear_balance(datos).relacion_max_min is None


# --- Evaluación offline ---------------------------------------------------------------------

def test_control_de_referencia_da_100():
    validacion = cargar_ejemplos(RUTA_VALIDACION)
    resultado = evaluar_respuestas(validacion, respuestas_de_referencia(validacion), "control_referencia")
    assert resultado["tipo"] == "checks_deterministas_offline"
    assert all(t == 1.0 for t in resultado["tasas"].values())
    assert resultado["incumplimiento_formato"] == 0.0


def test_evaluacion_detecta_respuestas_defectuosas():
    referencias = [ej("a", "red"), ej("b", "cuota", "esperar"), ej("c", "entorno", "instalar"), ej("d", "red")]
    respuestas = [
        "```json\n{\"categoria\": \"red\", \"accion_sugerida\": \"reintentar\"}\n```",           # no es JSON puro
        '{"categoria": "red", "accion_sugerida": "reintentar con backoff"}',                     # categoría errónea
        '{"categoria": "entorno", "accion_sugerida": "instalar", "confianza": 0.9}',             # clave extra
        '{"categoria": "red", "accion_sugerida": "reintentar con backoff"}',                     # correcta
    ]
    resultado = evaluar_respuestas(referencias, respuestas, "simulado")
    assert resultado["tasas"]["json_valido"] == 0.75
    assert resultado["tasas"]["claves_exactas"] == 0.5
    assert resultado["tasas"]["categoria_coincide"] == 0.5
    assert resultado["incumplimiento_formato"] == 0.5


def test_evaluacion_exige_misma_cantidad():
    with pytest.raises(ValueError):
        evaluar_respuestas([ej("a")], [], "x")
