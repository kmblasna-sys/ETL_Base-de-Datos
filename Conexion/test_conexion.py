from conexion import obtener_conexion
from mysql.connector import Error

def probar_enlace():
    """
    Realiza una prueba de conexión a la base de datos de Walmart.
    Ejecuta una consulta para obtener la versión del servidor MySQL y
    garantiza el cierre seguro de la conexión a través de un bloque try-except-finally.
    """
    conexion = None
    try:
        print("[*] Intentando conectar con el servidor MySQL...")
        conexion = obtener_conexion()
        
        if conexion and conexion.is_connected():
            cursor = conexion.cursor()
            # Consulta para verificar la versión del servidor de base de datos
            cursor.execute("SELECT VERSION();")
            db_version = cursor.fetchone()
            
            print("[+] ¡Enlace establecido con éxito!")
            print(f"[+] Versión de MySQL Server detectada: {db_version[0]}")
            cursor.close()
        else:
            print("[-] Prueba fallida. Revisa el estado del servidor MySQL y las credenciales en .env.")
            
    except Error as e:
        print(f"[-] Ocurrió un error inesperado al interactuar con la base de datos: {e}")
        
    finally:
        # El bloque finally garantiza que el recurso de red se libere sin importar el resultado
        if conexion and conexion.is_connected():
            conexion.close()
            print("[*] Conexión cerrada de forma limpia y segura.")

if __name__ == "__main__":
    probar_enlace()
