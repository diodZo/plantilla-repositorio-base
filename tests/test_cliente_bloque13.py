"""Pruebas locales sin red ni cuota. Ejecutar: python -m unittest discover -s tests -p 'test_cliente_bloque13.py' -v"""
import unittest
from unittest.mock import Mock, patch
import src.cliente as cliente


class TestClienteBloque13(unittest.TestCase):
    def setUp(self):
        cliente.costo_total_sesion = 0.0

    @patch('src.cliente.time.sleep')
    @patch('src.cliente.random.uniform', return_value=0)
    def test_backoff_exponencial(self, _, sleep):
        contador = 0
        def tarea():
            nonlocal contador
            contador += 1
            if contador < 3:
                raise TimeoutError('simulado')
            return 'ok'
        self.assertEqual(cliente.con_reintento(tarea), 'ok')
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [2, 4])

    @patch('src.cliente.time.sleep')
    def test_credencial_no_reintenta(self, sleep):
        tarea = Mock(side_effect=ValueError('credencial inválida'))
        with self.assertRaises(ValueError):
            cliente.con_reintento(tarea)
        self.assertEqual(tarea.call_count, 1)
        sleep.assert_not_called()

    def test_costos_acumulados(self):
        datos = {'usageMetadata': {'totalTokenCount': 1000}}
        self.assertAlmostEqual(cliente.registrar_costo(datos), 0.002)
        self.assertAlmostEqual(cliente.registrar_costo(datos), 0.002)
        self.assertAlmostEqual(cliente.costo_total_sesion, 0.004)

    @patch('src.cliente.requests.post')
    def test_http_429_reintentable(self, post):
        post.return_value.status_code = 429
        with self.assertRaises(TimeoutError):
            cliente.enviar_peticion('https://example.invalid', {}, {})

    @patch('src.cliente.requests.post')
    def test_http_401_no_reintentable(self, post):
        post.return_value.status_code = 401
        with self.assertRaises(ValueError):
            cliente.enviar_peticion('https://example.invalid', {}, {})


if __name__ == '__main__':
    unittest.main()
