# bot/handlers/messages.py
# -*- coding: utf-8 -*-

"""
Manejador para mensajes de texto normales enviados al bot.
"""

import logging
from typing import Dict, Any, List, Optional # Necesario para tipos

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode # Para formato Markdown/HTML

# Importar cliente de API y settings
try:
    # Asumiendo que la función para llamar a la API está en api_client.py
    from bot.services import api_client
    from bot.core.config import settings
    SERVICES_AVAILABLE = True
except ImportError:
    print("[ERROR messages.py] No se pudo importar api_client o settings. Usando dummies.")
    SERVICES_AVAILABLE = False
    # Dummies para que el archivo cargue
    class DummyApiClient:
        async def get_api_chat_response(self, message:str, session_id:str) -> dict:
            return {"answer": "ERROR: API Client no disponible", "sources": [], "session_id": session_id}
    api_client = DummyApiClient() # type: ignore
    class DummySettings: authorized_debug_user_ids: set = set()
    settings = DummySettings() # type: ignore

# Escapar caracteres para MarkdownV2 (si se usa ese parse_mode)
# from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)

# Mensaje de error genérico para el usuario si la API falla
API_ERROR_MESSAGE = "Lo siento, estoy teniendo problemas para conectar con mi cerebro principal en este momento. Por favor, intenta de nuevo en unos instantes."

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Procesa mensajes de texto, llama a la API KellyBot y devuelve la respuesta.
    Añade información de fuentes si el usuario está autorizado y tiene el modo debug activo.
    """
    if not update.message or not update.message.text:
        logger.debug("Recibido update sin mensaje de texto. Ignorando.")
        return # Ignorar si no hay mensaje o texto

    if not SERVICES_AVAILABLE:
         # Ya se logueó el error de importación
         if update.message: await update.message.reply_text("Lo siento, estoy experimentando problemas técnicos [SVC].")
         return

    user = update.effective_user
    chat_id = update.effective_chat.id if update.effective_chat else None
    message_text = update.message.text

    if not user:
         logger.warning("No se pudo obtener información del usuario del mensaje.")
         # Podríamos intentar responder al chat_id si lo tenemos
         if chat_id and update.message: await update.message.reply_text("No pude identificarte, lo siento.")
         return

    user_id = user.id
    # Crear un session_id único para el usuario
    session_id = f"tg_user_{user_id}"

    logger.info(f"Procesando mensaje de UserID {user_id}: '{message_text[:50]}...'")

    # Indicar al usuario que se está procesando (opcional)
    # await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    try:
        # Llamar al servicio que interactúa con tu API KellyBot
        response_data = await api_client.get_api_chat_response(
            message=message_text,
            session_id=session_id
        )

        # Verificar la respuesta de la API
        if not response_data or not isinstance(response_data, dict):
             logger.error(f"Respuesta inválida (no dict o None) del API Client para session {session_id}.")
             await update.message.reply_text(API_ERROR_MESSAGE)
             return

        base_answer = response_data.get("answer")
        sources = response_data.get("sources", []) # Obtener fuentes, default lista vacía

        if not base_answer:
             logger.error(f"Respuesta de API sin campo 'answer' para session {session_id}.")
             # Usar un mensaje genérico si la respuesta de la API es inesperada pero no falló la llamada
             base_answer = API_ERROR_MESSAGE
             sources = [] # No mostrar fuentes si la respuesta principal falló


        # --- Lógica para Añadir Fuentes (Debug) ---
        reply_message = base_answer # Empezar con la respuesta normal

        # Comprobar si el usuario está autorizado Y si activó el modo debug
        is_debug_authorized = user_id in settings.authorized_debug_user_ids
        # context.user_data requiere persistencia configurada en main.py
        is_debug_active = context.user_data.get('debug_mode', False) if context.user_data else False

        if is_debug_authorized and is_debug_active:
            logger.debug(f"Usuario {user_id} autorizado y con debug activo. Añadiendo fuentes.")
            if sources and isinstance(sources, list):
                source_lines = []
                for i, src in enumerate(sources):
                     if isinstance(src, dict):
                          src_id = src.get("source_id", "N/A")
                          score = src.get("score")
                          # Formato simple: ID (Score)
                          score_str = f" ({score:.3f})" if isinstance(score, float) else ""
                          # Escapar caracteres para MarkdownV2 si es necesario
                          # safe_id = escape_markdown(src_id, version=2)
                          source_lines.append(f"`{src_id}`{score_str}") # Usar backticks para monospace
                     else:
                          source_lines.append(f"Fuente {i+1} inválida")

                if source_lines:
                    sources_str = "\n • ".join(source_lines)
                    # Añadir sección de debug (usando formato Markdown)
                    # El separador \n\n---\n da un salto de línea y una línea horizontal
                    reply_message += f"\n\n---\n*Fuentes \\(Debug\\):*\n • {sources_str}" # Escapar ()*[] etc para MDV2
                else:
                    reply_message += "\n\n---\n*Fuentes \\(Debug\\):* Ninguna"
            else:
                 reply_message += "\n\n---\n*Fuentes \\(Debug\\):* Ninguna encontrada o formato inválido"
        # --- Fin Lógica Debug ---

        # Enviar respuesta final a Telegram
        # Usar ParseMode.MARKDOWN_V2 si formateaste el mensaje con *, _, `, etc.
        # ¡Recuerda escapar caracteres especiales si usas MarkdownV2! (., -, +, !)
        # Para simplificar, podrías quitar el formato y usar parse_mode=None
        await update.message.reply_text(reply_message, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        # Error al llamar a la API KellyBot o procesar su respuesta
        logger.exception(f"Error en handle_text_message para user {user_id}: {e}")
        # Enviar mensaje genérico al usuario
        if update.message: # Asegurar que todavía podemos responder
             await update.message.reply_text(API_ERROR_MESSAGE)


# --- Registro en main.py ---
# Necesitarás añadir esto en tu bot/main.py:
# from telegram.ext import MessageHandler, filters
# from bot.handlers import messages
# application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_text_message))