# bot/core/config.py
# -*- coding: utf-8 -*-

"""
Configuración centralizada para el Bot de Telegram KellyBot,
cargada desde .env o variables de entorno.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Any, Set, List, Literal, get_args

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import (
    Field,
    HttpUrl,
    SecretStr,
    FilePath, # Podría usarse si el archivo debe existir
    Path as PydanticPath, # Evitar conflicto con pathlib.Path
    field_validator,
    model_validator,
    ValidationError
)

# --- Definir Ruta Base del Proyecto ---
# Asume que config.py está en bot/core/
try:
    # Raíz del proyecto (kelly_telegram/)
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
except NameError:
    PROJECT_ROOT = Path.cwd()
    # Usar print aquí porque el logger aún no está configurado globalmente
    print(f"[ADVERTENCIA Config Bot] No se pudo determinar PROJECT_ROOT, usando CWD: {PROJECT_ROOT}")

# --- Tipos Específicos ---
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Configurar logger básico para este módulo (antes de que main.py lo configure)
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
     handler = logging.StreamHandler(sys.stderr)
     formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s')
     handler.setFormatter(formatter)
     logger.addHandler(handler)
     logger.setLevel(logging.WARNING)

# --- Clase Principal de Settings ---
class Settings(BaseSettings):
    """Carga y valida las configuraciones para el Bot de Telegram."""

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: SecretStr = Field(..., alias='TELEGRAM_BOT_TOKEN') # ¡Obligatorio!

    # --- Kelly API Backend ---
    KELLYBOT_API_URL: HttpUrl = Field(default="http://localhost:8000", alias='KELLYBOT_API_URL')
    # La clave para *llamar* a la API KellyBot (debe coincidir con API_ACCESS_KEY de la API)
    API_ACCESS_KEY: SecretStr = Field(..., alias='API_ACCESS_KEY') # ¡Obligatorio!
    API_TIMEOUT_CONNECT: float = Field(default=10.0, alias='API_TIMEOUT_CONNECT')
    API_TIMEOUT_READ: float = Field(default=180.0, alias='API_TIMEOUT_READ')

    # --- Configuración General del Bot ---
    LOG_LEVEL: LogLevel = Field(default='INFO', alias='LOG_LEVEL')
    # Opcional: Palabra clave para activar en grupos
    TRIGGER_WORD: Optional[str] = Field(default="kelly", alias='TRIGGER_WORD')

    # --- Configuración de Debug ---
    # Lista de IDs de usuario autorizados para ver debug (leído como string)
    AUTHORIZED_DEBUG_USERS_STR: Optional[str] = Field(default=None, alias='AUTHORIZED_DEBUG_USERS')
    # Campo calculado que contendrá el set de IDs enteros
    authorized_debug_user_ids: Set[int] = set()

    # --- Configuración de Persistencia (Opcional) ---
    PERSISTENCE_FILE_PATH: Optional[Path] = Field( # Usar Path de pathlib
        default=PROJECT_ROOT / "persistence" / "bot_data.pickle", # Default relativo a la raíz
        alias='PERSISTENCE_FILE_PATH'
    )

    # --- Configuración del Modelo Pydantic Settings ---
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / '.env', # Buscar .env en la raíz del proyecto del bot
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

    # --- Validadores ---
    @field_validator('LOG_LEVEL', mode='before')
    @classmethod
    def validate_log_level(cls, value: Any) -> str:
        """Valida y normaliza el nivel de log."""
        if not isinstance(value, str): raise ValueError("LOG_LEVEL debe ser str.")
        valid = get_args(LogLevel)
        upper_v = value.upper()
        if upper_v not in valid: raise ValueError(f"LOG_LEVEL inválido: '{value}'. Usar: {valid}")
        return upper_v

    # Validador para procesar la lista de usuarios de debug
    @model_validator(mode='after')
    def parse_debug_users_post(self) -> 'Settings':
        """Convierte AUTHORIZED_DEBUG_USERS_STR en un set de IDs enteros."""
        ids_set = set()
        # Usar getattr para acceso seguro al campo que viene del alias
        raw_value = getattr(self, 'AUTHORIZED_DEBUG_USERS_STR', None)
        if raw_value:
            try:
                ids_str_list = raw_value.split(',')
                for user_id_str in ids_str_list:
                    user_id_str = user_id_str.strip()
                    if user_id_str.isdigit():
                        ids_set.add(int(user_id_str))
                    elif user_id_str:
                        logger.warning(f"[Config Bot] ID inválido en AUTHORIZED_DEBUG_USERS: '{user_id_str}'")
            except Exception as e:
                logger.error(f"[Config Bot] Error parseando AUTHORIZED_DEBUG_USERS: {e}")
        # Asignar al campo calculado
        self.authorized_debug_user_ids = ids_set
        logger.debug(f"Usuarios debug cargados: {self.authorized_debug_user_ids}")
        return self

    # Validador/Resolvedor para la ruta de persistencia (opcional)
    @field_validator('PERSISTENCE_FILE_PATH', mode='before')
    @classmethod
    def resolve_persistence_path(cls, value: Any) -> Optional[Path]:
        """Resuelve la ruta del archivo de persistencia relativa a PROJECT_ROOT."""
        if value:
            path = Path(value)
            if not path.is_absolute():
                # Usar PROJECT_ROOT definido al inicio del archivo
                return (PROJECT_ROOT / path).resolve()
            return path
        return None

# --- Instancia Global de Configuración ---
try:
    settings = Settings()
except ValidationError as e:
    logging.basicConfig(level='CRITICAL')
    logger = logging.getLogger(__name__) # Usar logger local
    logger.critical("!!! Error CRÍTICO de Validación de Configuración (Bot) !!!")
    logger.critical(f"Revisa tu archivo .env ({PROJECT_ROOT / '.env'}):")
    logger.critical(e)
    sys.exit("Error fatal de configuración del bot.")
except Exception as e:
    logging.basicConfig(level='CRITICAL')
    logger = logging.getLogger(__name__)
    logger.critical(f"!!! Error CRÍTICO Inesperado al Cargar Configuración (Bot) !!!: {e}", exc_info=True)
    sys.exit("Error fatal inesperado cargando configuración del bot.")

# --- Bloque de prueba opcional ---
if __name__ == "__main__":
    print("--- Configuración Cargada para Kelly Telegram Bot ---")
    if 'settings' in locals():
         # Usar model_dump para excluir SecretStr por defecto
         print(settings.model_dump_json(indent=2))
         print("\n--- Valores Secretos (Ejemplo Acceso) ---")
         print(f"Telegram Token: {'******' if settings.TELEGRAM_BOT_TOKEN else 'None'}")
         print(f"Kelly API Key: {'******' if settings.API_ACCESS_KEY else 'None'}")
         if settings.MONGO_URI: print(f"Mongo URI: {'******'}")
         print(f"Authorized Debug IDs: {settings.authorized_debug_user_ids}")
    else:
         print("La instancia 'settings' no pudo ser creada.")