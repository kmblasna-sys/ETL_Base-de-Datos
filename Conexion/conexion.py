import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env en el mismo directorio
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

def obtener_conexion():
    """
    Establece y retorna una conexión activa a la base de datos MySQL.
    Utiliza las credenciales encapsuladas en el archivo externo .env.
    """
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "Mineria_BD")
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"[-] Error al intentar establecer la conexión: {e}")
        return None
