# tests/handlers/test_messages.py
# -*- coding: utf-8 -*-

"""
Pruebas unitarias para el manejador de mensajes de texto (bot/handlers/messages.py).
CORREGIDO: Añadida importación de typing.Optional y otros.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
# NUEVO: Importar tipos necesarios de typing
from typing import Optional, List, Dict, Any

# Importar Update y ContextTypes (o usar MagicMock directamente)
try:
     from telegram import Update, User, Chat, Message
     from telegram.ext import ContextTypes
     from telegram.constants import ParseMode # Importar ParseMode también
     PTB_AVAILABLE = True
except ImportError:
     # Si PTB no está en el entorno de prueba por alguna razón, mockear todo
     Update = MagicMock()
     ContextTypes = MagicMock()
     User = MagicMock()
     Chat = MagicMock()
     Message = MagicMock()
     ParseMode = MagicMock() # Dummy para ParseMode
     PTB_AVAILABLE = False


# Importar la función del handler que queremos probar y settings
# Asegúrate de que la ruta sea correcta
try:
    from bot.handlers.messages import handle_text_message
    from bot.core.config import settings
    # Importar el cliente API dummy/real para obtener el mensaje de error default
    from bot.services import api_client
    HANDLER_AVAILABLE = True
    # Verificar si settings tiene el atributo esperado (puede ser el dummy si config falló)
    if not hasattr(settings, 'authorized_debug_user_ids'):
         print("[WARN test_messages.py] settings no tiene 'authorized_debug_user_ids'. Usando set vacío.")
         settings.authorized_debug_user_ids = set() # Añadir atributo si falta en dummy
except ImportError:
     pytest.skip("No se pudo importar el handler o la configuración, saltando pruebas.", allow_module_level=True)
     HANDLER_AVAILABLE = False

# Marcar todas las pruebas como async
pytestmark = pytest.mark.asyncio


# --- Funciones Auxiliares de Prueba ---

# Usar Optional importado de typing
def create_mock_update(user_id: int, chat_id: int, text: Optional[str]) -> MagicMock:
    """Crea un objeto Update simulado con la estructura mínima necesaria."""
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.first_name = f"TestUser{user_id}"

    mock_chat = MagicMock(spec=Chat)
    mock_chat.id = chat_id

    mock_message = MagicMock(spec=Message)
    mock_message.text = text
    # Simular reply_text como AsyncMock
    mock_message.reply_text = AsyncMock()

    mock_update = MagicMock(spec=Update)
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_update.message = mock_message
    return mock_update

def create_mock_context(user_data: Optional[dict] = None) -> MagicMock:
     """Crea un objeto Context simulado."""
     mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
     mock_context.user_data = user_data if user_data is not None else {}
     return mock_context

# --- Pruebas (Sin cambios en la lógica de las pruebas) ---

# Datos de prueba (sin cambios)
TEST_API_KEY = "test-api-key-123" # No usado directamente aquí, pero sí en el mock de deps
HEADERS = {"Authorization": f"Bearer {TEST_API_KEY}"}
VALID_CHAT_PAYLOAD = {"message": "Hola", "session_id": "test-session-chat"}
MOCKED_RAG_RESPONSE = {
    "answer": "Respuesta simulada por el RAG.",
    "sources": [{"source_id": "DOC_SIMULADO_q0", "score": 0.99}]
}

# @pytest.mark.skipif(not HANDLER_AVAILABLE, reason="Handler o dependencias no disponibles") # Opcional: saltar si falla import
async def test_handle_message_normal_user(mocker): # Quitar 'client' si no se usa directamente aquí
    """Prueba la respuesta para un usuario normal (sin debug)."""
    mock_api_call = mocker.patch("bot.handlers.messages.api_client.get_api_chat_response", new_callable=AsyncMock)
    mock_api_call.return_value = MOCKED_RAG_RESPONSE
    mocker.patch.object(settings, 'authorized_debug_user_ids', set())

    user_id, chat_id = 123, 123
    update = create_mock_update(user_id, chat_id, "Hola bot")
    context = create_mock_context()

    await handle_text_message(update, context)

    mock_api_call.assert_awaited_once_with(message="Hola bot", session_id=f"tg_user_{user_id}")
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert call_args[0] == "Respuesta simulada por el RAG."
    assert "Fuentes (Debug)" not in call_args[0]
    assert call_kwargs.get("parse_mode") != ParseMode.MARKDOWN_V2


async def test_handle_message_debug_user_debug_off(mocker):
    """Prueba la respuesta para un usuario autorizado pero con debug desactivado."""
    mock_api_call = mocker.patch("bot.handlers.messages.api_client.get_api_chat_response", new_callable=AsyncMock)
    mock_api_call.return_value = MOCKED_RAG_RESPONSE
    debug_user_id = 987
    mocker.patch.object(settings, 'authorized_debug_user_ids', {debug_user_id})

    update = create_mock_update(debug_user_id, 987, "Pregunta")
    context = create_mock_context(user_data={'debug_mode': False}) # Debug OFF

    await handle_text_message(update, context)

    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert call_args[0] == "Respuesta simulada por el RAG."
    assert "Fuentes (Debug)" not in call_args[0]
    assert call_kwargs.get("parse_mode") != ParseMode.MARKDOWN_V2


async def test_handle_message_debug_user_debug_on(mocker):
    """Prueba la respuesta para un usuario autorizado Y con debug activado."""
    mock_api_call = mocker.patch("bot.handlers.messages.api_client.get_api_chat_response", new_callable=AsyncMock)
    # Respuesta simulada con múltiples fuentes
    mock_api_response_multi = {
        "answer": "Respuesta detallada.",
        "sources": [
            {"source_id": "FILE1_q0", "score": 0.95},
            {"source_id": "priority_context", "score": 1.0}
        ]
    }
    mock_api_call.return_value = mock_api_response_multi
    debug_user_id = 987
    mocker.patch.object(settings, 'authorized_debug_user_ids', {debug_user_id}) # Autorizado

    update = create_mock_update(debug_user_id, 987, "Pregunta debug")
    context = create_mock_context(user_data={'debug_mode': True}) # Debug ON

    await handle_text_message(update, context)

    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    reply_text = call_args[0]
    assert reply_text.startswith("Respuesta detallada.")
    assert "Fuentes \\(Debug\\):" in reply_text # Verificar sección debug (con escape MDV2)
    assert "`FILE1_q0` (0.950)" in reply_text # Verificar formato fuente 1
    assert "`priority_context` (1.000)" in reply_text # Verificar formato fuente 2
    assert call_kwargs.get("parse_mode") == ParseMode.MARKDOWN_V2


async def test_handle_message_api_error(mocker):
    """Prueba cómo responde el handler si la llamada a la API falla."""
    # Configurar mock para devolver una respuesta de error simulada del api_client
    mock_api_call = mocker.patch("bot.handlers.messages.api_client.get_api_chat_response", new_callable=AsyncMock)
    # Asumiendo que DEFAULT_API_ERROR_RESPONSE está definido en api_client
    # Importarlo o definirlo aquí para la aserción
    error_response_text = "Mensaje de error simulado desde API Client"
    mock_api_call.return_value = {"answer": error_response_text, "sources": [], "session_id":"err-sess"}

    mocker.patch.object(settings, 'authorized_debug_user_ids', set())
    user_id, chat_id = 456, 456
    update = create_mock_update(user_id, chat_id, "Pregunta que causa error")
    context = create_mock_context()

    await handle_text_message(update, context)

    mock_api_call.assert_awaited_once_with(message="Pregunta que causa error", session_id=f"tg_user_{user_id}")
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert error_response_text in call_args[0]


async def test_handle_message_no_text():
    """Prueba que ignora mensajes sin texto."""
    # No necesita mocker porque no debería llamar a otros módulos
    update = create_mock_update(111, 111, None) # Mensaje sin texto
    context = create_mock_context()
    await handle_text_message(update, context)
    # Verificar que NO se llamó a reply_text
    update.message.reply_text.assert_not_awaited()