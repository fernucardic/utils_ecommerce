import pandas as pd

class ChangeStatus():
    def __init__(self):
        print("\t Inicializando datos...")
    
    def load_data(self):
        self.general_CO = pd.read_csv("../Data/Generales/General-CO.csv", low_memory=False)
        self.general_DS = pd.read_csv("../Data/Generales/General-DS.csv", low_memory=False)
        self.general_TE = pd.read_csv("../Data/Generales/General-TE.csv", low_memory=False)
        self.general_TS = pd.read_csv("../Data/Generales/General-TS.csv", low_memory=False)
        self.general_CA = pd.read_csv("../Data/Generales/General-CA.csv", low_memory=False)

def print_menu_hero():
    print("\n=============== SISTEMA DE PAUSADO/ACTIVACION CARDIC AUTOMOTRIZ ===============")
    print("\t Selecciona una opción:")
    print("\t 1. Pausar codigos")
    print("\t 2. Activar codigos")

if __name__ == '__main__':
    print_menu_hero()
    option = int(input("\t Digita tu seleccion: "))

    if option == 1:
        print("Pausando elementos")
    elif option == 2:
        print("Activado automatico")
    else:
        while(option != 1 and option != 2):
            print("\t ERROR Opcion no valida digita nuevamente tu seleccion")
            option = int(input("\t Digita tu seleccion: "))
