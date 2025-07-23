from tqdm import tqdm
import time

for i in tqdm(range(100), desc="Instalando paquetes"):
    time.sleep(0.05)
