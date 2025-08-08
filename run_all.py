import subprocess
import threading
import time

def run_generate_data():
    print("📥 [START] Pobieranie danych i generowanie wykresów...")
    subprocess.run(["python", "generate_data.py"])
    print("✅ [GOTOWE] Dane i wykresy gotowe.")

def run_scheduler():
    print("⏰ [START] Scheduler alertów...")
    subprocess.run(["python", "scheduler.py"])

def run_dashboard():
    print("📊 [START] Dashboard...")
    subprocess.run(["python", "dashboard.py"])

if __name__ == "__main__":
    # Najpierw pobierz dane
    run_generate_data()

    # Następnie uruchom równolegle alerty i dashboard
    t1 = threading.Thread(target=run_scheduler)
    t2 = threading.Thread(target=run_dashboard)

    t1.start()
    time.sleep(2)  # Mały odstęp
    t2.start()

    t1.join()
    t2.join()
