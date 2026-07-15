import os
import mysql.connector
from mysql.connector import Error
from mysql.connector.conversion import MySQLConverter
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env en el mismo directorio
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

class CustomConverter(MySQLConverter):
    """
    Convertidor personalizado para evitar la deserialización de fechas cero ('0000-00-00') como None.
    Esto permite que la interfaz muestre el valor real en lugar de NULL.
    """
    def _date_to_python(self, value, dsc=None):
        if value == b'0000-00-00' or value == b'00:00:00':
            return '0000-00-00'
        return super()._date_to_python(value, dsc)

    def _NEWDATE_to_python(self, value, dsc=None):
        if value == b'0000-00-00' or value == b'00:00:00':
            return '0000-00-00'
        return super()._NEWDATE_to_python(value, dsc)

def obtener_conexion():
    """
    Establece y retorna una conexión activa a la base de datos MySQL.
    Utiliza las credenciales encapsuladas en el archivo externo .env y el convertidor personalizado.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "Mineria_BD"),
            converter_class=CustomConverter
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[-] Error al intentar establecer la conexión: {e}")
        return None
