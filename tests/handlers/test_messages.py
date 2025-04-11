# tests/handlers/test_messages.py
# -*- coding: utf-8 -*-

"""
Pruebas unitarias para el manejador de mensajes de texto (bot/handlers/messages.py).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Importar Update y ContextTypes (o usar MagicMock directamente)
try:
     from telegram import Update, User, Chat, Message
     from telegram.ext import ContextTypes
     PTB_AVAILABLE = True
except ImportError:
     # Si PTB no está en el entorno de prueba por alguna razón, mockear todo
     Update = MagicMock()
     ContextTypes = MagicMock()
     User = MagicMock()
     Chat = MagicMock()
     Message = MagicMock()
     PTB_AVAILABLE = False


# Importar la función del handler que queremos probar
# Asegúrate de que la ruta sea correcta
try:
    from bot.handlers.messages import handle_text_message
    from bot.core.config import settings # Necesitamos settings para los usuarios debug
    HANDLER_AVAILABLE = True
except ImportError:
     pytest.skip("No se pudo importar el handler o la configuración, saltando pruebas.", allow_module_level=True)
     HANDLER_AVAILABLE = False # Para satisfacer linters

# Marcar todas las pruebas como async
pytestmark = pytest.mark.asyncio


# --- Funciones Auxiliares de Prueba ---

def create_mock_update(user_id: int, chat_id: int, text: Optional[str]) -> MagicMock:
    """Crea un objeto Update simulado con la estructura mínima necesaria."""
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.first_name = f"TestUser{user_id}"

    mock_chat = MagicMock(spec=Chat)
    mock_chat.id = chat_id

    mock_message = MagicMock(spec=Message)
    mock_message.text = text
    # Simular el método reply_text como una función async mockeada
    mock_message.reply_text = AsyncMock()

    mock_update = MagicMock(spec=Update)
    mock_update.effective_user = mock_user
    mock_update.effective_chat = mock_chat
    mock_update.message = mock_message
    return mock_update

def create_mock_context(user_data: Optional[dict] = None) -> MagicMock:
     """Crea un objeto Context simulado."""
     mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
     # Simular user_data como un diccionario
     mock_context.user_data = user_data if user_data is not None else {}
     return mock_context

# --- Pruebas ---

@patch("bot.handlers.messages.api_client.get_api_chat_response") # Mockear la llamada a la API
async def test_handle_message_normal_user(mock_api_call, mocker):
    """Prueba la respuesta para un usuario normal (sin debug)."""
    # Configurar mock de la API para devolver respuesta exitosa
    mock_api_response = {
        "answer": "Respuesta de la API.",
        "sources": [{"source_id": "SRC1", "score": 0.9}]
    }
    mock_api_call.return_value = mock_api_response

    # Simular usuario NO autorizado para debug
    mocker.patch.object(settings, 'authorized_debug_user_ids', set()) # Vacío

    # Crear update y context simulados
    user_id = 123
    chat_id = 123
    update = create_mock_update(user_id, chat_id, "Hola bot")
    context = create_mock_context()

    # Ejecutar el handler
    await handle_text_message(update, context)

    # Verificar que se llamó a la API
    mock_api_call.assert_awaited_once_with(message="Hola bot", session_id=f"tg_user_{user_id}")

    # Verificar que se respondió al usuario SOLO con el 'answer'
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert call_args[0] == "Respuesta de la API." # Verificar texto exacto
    assert "Fuentes (Debug)" not in call_args[0] # Asegurar que NO contenga debug info
    # Verificar parse_mode (debería ser None o no estar si no hay formato)
    assert call_kwargs.get("parse_mode") != ParseMode.MARKDOWN_V2


@patch("bot.handlers.messages.api_client.get_api_chat_response")
async def test_handle_message_debug_user_debug_off(mock_api_call, mocker):
    """Prueba la respuesta para un usuario autorizado pero con debug desactivado."""
    mock_api_response = {"answer": "Respuesta API.", "sources": [{"source_id": "SRC1", "score": 0.9}]}
    mock_api_call.return_value = mock_api_response
    debug_user_id = 987
    mocker.patch.object(settings, 'authorized_debug_user_ids', {debug_user_id}) # Autorizado

    update = create_mock_update(debug_user_id, 987, "Pregunta")
    # Simular que el modo debug NO está activo en user_data
    context = create_mock_context(user_data={'debug_mode': False})

    await handle_text_message(update, context)

    # Verificar que se respondió SOLO con el 'answer'
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert call_args[0] == "Respuesta API."
    assert "Fuentes (Debug)" not in call_args[0]
    assert call_kwargs.get("parse_mode") != ParseMode.MARKDOWN_V2

@patch("bot.handlers.messages.api_client.get_api_chat_response")
async def test_handle_message_debug_user_debug_on(mock_api_call, mocker):
    """Prueba la respuesta para un usuario autorizado Y con debug activado."""
    mock_api_response = {
        "answer": "Respuesta detallada.",
        "sources": [
            {"source_id": "FILE1_q0", "score": 0.95},
            {"source_id": "priority_context", "score": 1.0}
        ]
    }
    mock_api_call.return_value = mock_api_response
    debug_user_id = 987
    mocker.patch.object(settings, 'authorized_debug_user_ids', {debug_user_id}) # Autorizado

    update = create_mock_update(debug_user_id, 987, "Pregunta debug")
    # Simular que el modo debug SÍ está activo en user_data
    context = create_mock_context(user_data={'debug_mode': True})

    await handle_text_message(update, context)

    # Verificar que se respondió CON el 'answer' Y las fuentes formateadas
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    reply_text = call_args[0]
    assert reply_text.startswith("Respuesta detallada.")
    assert "Fuentes \\(Debug\\):" in reply_text # Verificar sección debug (con escape para MDV2)
    assert "`FILE1_q0` (0.950)" in reply_text # Verificar formato fuente 1
    assert "`priority_context` (1.000)" in reply_text # Verificar formato fuente 2
    # Verificar que se usó ParseMode correcto
    assert call_kwargs.get("parse_mode") == ParseMode.MARKDOWN_V2


@patch("bot.handlers.messages.api_client.get_api_chat_response")
async def test_handle_message_api_error(mock_api_call, mocker):
    """Prueba cómo responde el handler si la llamada a la API falla."""
    # Configurar mock para devolver una respuesta de error simulada
    mock_api_call.return_value = api_client.DEFAULT_API_ERROR_RESPONSE

    # Simular usuario normal
    mocker.patch.object(settings, 'authorized_debug_user_ids', set())
    user_id, chat_id = 456, 456
    update = create_mock_update(user_id, chat_id, "Pregunta que causará error")
    context = create_mock_context()

    await handle_text_message(update, context)

    # Verificar que se llamó a la API
    mock_api_call.assert_awaited_once_with(message="Pregunta que causará error", session_id=f"tg_user_{user_id}")

    # Verificar que se envió el mensaje de error por defecto del API Client
    update.message.reply_text.assert_awaited_once()
    call_args, call_kwargs = update.message.reply_text.call_args
    assert api_client.DEFAULT_API_ERROR_RESPONSE["answer"] in call_args[0]

async def test_handle_message_no_text(mocker):
    """Prueba que ignora mensajes sin texto."""
    # Mockear seguridad por si acaso (aunque no debería llegar a llamar a la API)
    mocker.patch("app.api.deps.get_api_key", return_value="dummy") # Si test_chat importara esto

    update = create_mock_update(111, 111, None) # Mensaje sin texto
    context = create_mock_context()
    await handle_text_message(update, context)
    # Verificar que NO se llamó a reply_text
    update.message.reply_text.assert_not_awaited()