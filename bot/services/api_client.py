# bot/services/api_client.py
# -*- coding: utf-8 -*-

"""
Servicio para realizar llamadas a la API backend de KellyBot (FastAPI).
"""

import logging
from typing import Dict, Any, Optional, List

# Usar httpx para llamadas async a la API
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    print("[ERROR api_client.py] httpx no está instalado. Ejecuta: pip install httpx")
    HTTPX_AVAILABLE = False

# Importar configuración
try:
    from bot.core.config import settings
    CONFIG_LOADED = True
except ImportError:
    print("[ERROR api_client.py] No se pudo importar 'settings'. Usando defaults.")
    # Dummy settings
    class DummySettings:
        KELLYBOT_API_URL: str = "http://localhost:8000"
        API_ACCESS_KEY: Optional[Any] = None # Usar Any para SecretStr
        API_TIMEOUT_CONNECT: float = 10.0
        API_TIMEOUT_READ: float = 180.0
    settings = DummySettings() # type: ignore
    CONFIG_LOADED = False
except Exception as config_err:
     print(f"[ERROR api_client.py] Error al importar/validar 'settings': {config_err}.")
     # ... (Definir DummySettings como antes) ...
     settings = DummySettings(); CONFIG_LOADED = False


logger = logging.getLogger(__name__)

# --- Constante para respuesta de error ---
DEFAULT_API_ERROR_RESPONSE = {
    "answer": "Lo siento, no pude comunicarme con el sistema principal en este momento. Por favor, inténtalo de nuevo.",
    "sources": [],
    "session_id": None # El handler lo añadirá si es posible
}

# --- Cliente HTTPX (Compartido y Asíncrono) ---
# Crear una instancia global (o usar un patrón más avanzado como inyección)
# Se inicializará al importar el módulo
# En producción, considera manejar el ciclo de vida del cliente (startup/shutdown)
# _api_client: Optional[httpx.AsyncClient] = None

# def get_api_client() -> httpx.AsyncClient:
#      """Inicializa o devuelve el cliente httpx."""
#      global _api_client
#      if _api_client is None:
#           logger.info("Creando instancia global de httpx.AsyncClient")
#           # Configurar timeouts desde settings
#           timeout_config = httpx.Timeout(
#                settings.API_TIMEOUT_CONNECT,
#                read=settings.API_TIMEOUT_READ
#           )
#           _api_client = httpx.AsyncClient(timeout=timeout_config)
#      return _api_client

# Alternativa más simple: Crear cliente por petición con 'async with'


# --- Función Principal del Cliente API ---

async def get_api_chat_response(message: str, session_id: str) -> Dict[str, Any]:
    """
    Llama al endpoint /api/v1/chat del backend Kelly API.

    Args:
        message: Mensaje del usuario.
        session_id: ID de la sesión actual.

    Returns:
        Un diccionario con la respuesta de la API (incluyendo 'answer', 'sources', 'session_id')
        o un diccionario de error si la llamada falla.
    """
    if not HTTPX_AVAILABLE or not CONFIG_LOADED:
        logger.critical("Dependencias (httpx) o Configuración no disponibles para API Client.")
        return {**DEFAULT_API_ERROR_RESPONSE, "session_id": session_id}

    # Obtener configuración necesaria
    base_api_url = str(getattr(settings, 'KELLYBOT_API_URL', None))
    api_key_secret = getattr(settings, 'API_ACCESS_KEY', None)
    api_key = api_key_secret.get_secret_value() if api_key_secret and hasattr(api_key_secret, 'get_secret_value') else None
    connect_timeout = getattr(settings, 'API_TIMEOUT_CONNECT', 10.0)
    read_timeout = getattr(settings, 'API_TIMEOUT_READ', 180.0)

    # Validar configuración esencial
    if not base_api_url or not api_key:
        logger.error("KELLYBOT_API_URL o API_ACCESS_KEY no configuradas correctamente.")
        return {**DEFAULT_API_ERROR_RESPONSE, "session_id": session_id}

    # Construir URL, asegurando que no haya doble barra si base_api_url ya la tiene
    target_url = f"{base_api_url.rstrip('/')}/api/v1/chat"
    # Construir Payload
    payload = {"message": message, "session_id": session_id}
    # Construir Headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json" # Buena práctica indicar qué se acepta
    }
    # Configurar Timeouts
    timeout_config = httpx.Timeout(connect_timeout, read=read_timeout)

    logger.debug(f"Llamando a Kelly API: POST {target_url}")
    # Usar 'async with' para crear y cerrar el cliente en cada llamada (más simple)
    # En producción con alta carga, considera un cliente compartido.
    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                url=target_url,
                json=payload,
                headers=headers
            )

            # Lanzar excepción para errores HTTP (4xx, 5xx)
            response.raise_for_status()

            # Si llegamos aquí, es un 2xx
            logger.debug(f"Respuesta recibida de Kelly API ({response.status_code}).")
            # Devolver el cuerpo JSON parseado
            # Añadir session_id si la API no lo devuelve (aunque debería)
            response_json = response.json()
            if "session_id" not in response_json:
                 response_json["session_id"] = session_id
            return response_json

    except httpx.TimeoutException as e:
        logger.error(f"Timeout al llamar a Kelly API ({target_url}): {e}")
        return {**DEFAULT_API_ERROR_RESPONSE, "answer": "Lo siento, la respuesta está tardando demasiado.", "session_id": session_id}
    except httpx.RequestError as e:
        # Errores de conexión, DNS, etc.
        logger.error(f"Error de red/conexión al llamar a Kelly API ({target_url}): {e}")
        return {**DEFAULT_API_ERROR_RESPONSE, "answer": "Lo siento, no pude conectarme con el sistema principal.", "session_id": session_id}
    except httpx.HTTPStatusError as e:
        # Errores HTTP 4xx/5xx que no capturamos explícitamente antes
        logger.error(f"Error HTTP {e.response.status_code} recibido de Kelly API ({target_url}). Respuesta: {e.response.text[:200]}...")
        # Podríamos intentar devolver el 'detail' si existe y es un error del cliente (4xx)
        error_detail = "Error inesperado del servidor principal."
        try:
             detail = e.response.json().get("detail")
             if detail and e.response.status_code < 500: # Mostrar detalle solo para errores "cliente" (4xx)
                 error_detail = f"Error {e.response.status_code}: {detail}"
             elif e.response.status_code == 401:
                  error_detail = "Error de autenticación con la API interna. Contacta al administrador."

        except Exception: pass # Ignorar si el cuerpo no es JSON o falta 'detail'
        return {**DEFAULT_API_ERROR_RESPONSE, "answer": error_detail, "session_id": session_id}
    except json.JSONDecodeError as e:
        logger.error(f"Error decodificando respuesta JSON de Kelly API ({target_url}): {e}. Respuesta: {response.text[:200]}...")
        return {**DEFAULT_API_ERROR_RESPONSE, "session_id": session_id}
    except Exception as e:
        # Capturar cualquier otro error inesperado
        logger.exception(f"Error inesperado en api_client al llamar a Kelly API: {e}")
        return {**DEFAULT_API_ERROR_RESPONSE, "session_id": session_id}


# --- Bloque para pruebas rápidas (requiere API corriendo y .env) ---
if __name__ == "__main__":
    import asyncio

    async def test_api_client():
        logging.basicConfig(level=logging.DEBUG)
        print("--- Probando API Client (Requiere Kelly API corriendo y .env) ---")

        if not HTTPX_AVAILABLE or not CONFIG_LOADED:
            print("Dependencias (httpx) o Configuración no disponibles.")
            return

        test_message = "¿Qué es MiAdminXML?"
        test_session = "test-client-session-001"

        print(f"\nEnviando pregunta: '{test_message}'")
        response = await get_api_chat_response(test_message, test_session)

        print("\n--- Respuesta Recibida ---")
        print(json.dumps(response, indent=2, ensure_ascii=False))

    try:
        asyncio.run(test_api_client())
    except RuntimeError:
         print("Podría necesitarse un loop diferente si ya hay uno corriendo.")
    except Exception as e_main:
         print(f"Error ejecutando la prueba: {e_main}")