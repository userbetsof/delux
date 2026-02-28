import subprocess
import sys

def run_python_file(filename):
    try:
        result = subprocess.run(
            [sys.executable, filename],  # sys.executable использует текущий интерпретатор Python
            capture_output=True,
            text=True,
            check=True  # Вызывает исключение при ненулевом коде возврата
        )
        print("Файл успешно выполнен!")
        print(f"Вывод:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при выполнении файла {filename}:")
        print(f"Код ошибки: {e.returncode}")
        print(f"Вывод:\n{e.stdout}")
        print(f"Ошибки:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Файл {filename} не найден!")
        return False

# Использование
if __name__ == "__main__":
    filename = "db.py"  # Укажите имя вашего файла
    run_python_file(filename)