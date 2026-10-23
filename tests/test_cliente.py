
import unittest
from unittest.mock import patch

from src.cliente import con_reintento


class TestCliente(unittest.TestCase):

    @patch("src.cliente.time.sleep")
    def test_reintento_exitoso(self, mock_sleep):
        intentos = 0

        def peticion():
            nonlocal intentos
            intentos += 1

            if intentos < 3:
                raise RuntimeError(
                    "Gemini respondió con el error 503"
                )

            return {"respuesta": "OK"}

        resultado = con_reintento(peticion)

        self.assertEqual(resultado["respuesta"], "OK")
        self.assertEqual(intentos, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("src.cliente.time.sleep")
    def test_no_reintentar_credencial(self, mock_sleep):
        intentos = 0

        def peticion():
            nonlocal intentos
            intentos += 1
            raise RuntimeError(
                "Gemini respondió con el error 401"
            )

        with self.assertRaises(RuntimeError):
            con_reintento(peticion)

        self.assertEqual(intentos, 1)
        mock_sleep.assert_not_called()

    @patch("src.cliente.time.sleep")
    def test_reintentos_agotados(self, mock_sleep):
        def peticion():
            raise RuntimeError(
                "Gemini respondió con el error 503"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "tras varios intentos"
        ):
            con_reintento(peticion)

        self.assertEqual(mock_sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
