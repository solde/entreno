"""Productos locales de España y Cataluña y calendario de temporada. Valores ORIENTATIVOS por 100 g.
Fila: (nombre, categoria, kcal, proteina, hidratos, grasa, fibra, porcion_g, meses, origen)
meses: "" = todo el año; "11-3" = noviembre a marzo (admite el salto de año); "6-9,12" = lista. origen: "cat" (Cataluña) o "es" (resto de España)."""
P, L, C, V, F, N, O, LEG = "Proteínas", "Lácteos y huevos", "Cereales y tubérculos", "Verduras", "Frutas", "Frutos secos, grasas y dulces", "Otros", "Legumbres"

# meses de temporada de los alimentos que ya estaban en la base (por nombre exacto)
SEASON_EXISTING = {
    "Brócoli": "10-4", "Coliflor": "10-4", "Espinacas": "10-5", "Lechuga": "3-11", "Tomate": "6-9", "Pepino": "5-9", "Pimiento rojo": "6-10", "Calabacín": "5-10",
    "Berenjena": "6-10", "Judías verdes": "5-10", "Aguacate": "10-5", "Calabaza": "9-12", "Espárragos": "3-6", "Repollo / col": "10-3", "Guisantes": "3-6",
    "Manzana": "9-3", "Naranja": "11-5", "Fresas": "3-6", "Arándanos": "5-8", "Uvas": "8-11", "Pera": "8-12", "Kiwi": "11-4", "Melón": "6-10", "Sandía": "6-9",
    "Mango": "9-11", "Melocotón": "5-9", "Boniato (cocido)": "10-2", "Almendras": "", "Nueces": "9-12",
}
# alimentos que ya estaban y son típicos de aquí
ORIGIN_EXISTING = {"Jamón serrano": "es", "Aceite de oliva": "es", "Tomate frito (salsa)": "es", "Merluza (cruda)": "es", "Bacalao (cocinado)": "es", "Sardinas en lata (escurridas)": "es",
                   "Garbanzos (cocidos)": "es", "Lentejas (cocidas)": "es", "Alubias blancas (cocidas)": "es", "Queso curado": "es", "Almendras": "es", "Nueces": "es", "Vino tinto": "es"}

LOCAL = [
 # pescado y marisco
 ("Anchoas (L'Escala, en aceite, escurridas)", P, 210, 29, 0, 10, 0, 20, "", "cat"), ("Boquerones en vinagre", P, 140, 19, 0.5, 7, 0, 50, "", "es"),
 ("Boquerón fresco", P, 130, 18, 0, 6, 0, 120, "4-10", "es"), ("Sardina fresca", P, 135, 21, 0, 5.5, 0, 120, "5-10", "es"), ("Caballa / verdel", P, 205, 19, 0, 14, 0, 150, "3-6", "es"),
 ("Bonito del norte (cocido)", P, 150, 25, 0, 5, 0, 120, "6-10", "es"), ("Rape (cocinado)", P, 76, 16, 0, 1.5, 0, 150, "", "es"), ("Dorada", P, 120, 20, 0, 4, 0, 150, "", "es"),
 ("Lubina", P, 124, 24, 0, 3, 0, 150, "", "es"), ("Rodaballo", P, 95, 16.5, 0, 3, 0, 150, "", "es"), ("Pulpo (cocido)", P, 82, 15, 2, 1, 0, 150, "", "es"),
 ("Calamar", P, 92, 16, 3, 1.4, 0, 120, "", "es"), ("Sepia", P, 79, 16, 0.8, 0.7, 0, 150, "", "cat"), ("Mejillones (cocidos)", P, 86, 12, 3.7, 2.2, 0, 100, "10-4", "es"),
 ("Almejas (cocidas)", P, 148, 26, 5, 2, 0, 100, "", "es"), ("Gamba roja de Palamós (cocida)", P, 90, 19, 0, 1.2, 0, 100, "", "cat"), ("Bacalao salado (desalado, crudo)", P, 100, 22, 0, 1, 0, 150, "", "cat"),
 ("Caracoles (cocidos)", P, 90, 16, 2, 1.4, 0, 100, "", "cat"),
 # carnes y embutidos
 ("Botifarra blanca (cocinada)", P, 265, 15, 1, 22, 0, 100, "", "cat"), ("Botifarra negra (cocinada)", P, 290, 13, 4, 25, 0, 80, "", "cat"), ("Fuet", P, 460, 27, 3, 38, 0, 30, "", "cat"),
 ("Llonganissa / longaniza", P, 410, 24, 1.5, 34, 0, 30, "", "cat"), ("Chorizo", P, 455, 24, 2, 38, 0, 30, "", "es"), ("Morcilla de cebolla", P, 380, 15, 7, 32, 0, 50, "", "es"),
 ("Sobrasada", P, 480, 13, 1.5, 46, 0, 20, "", "es"), ("Lomo embuchado", P, 330, 50, 1, 14, 0, 30, "", "es"), ("Jamón ibérico de bellota", P, 375, 33, 0, 27, 0, 30, "", "es"),
 ("Cecina", P, 210, 38, 0.5, 6, 0, 30, "", "es"), ("Cordero lechal (asado)", P, 250, 25, 0, 17, 0, 120, "12-5", "es"), ("Cabrito (asado)", P, 220, 27, 0, 12, 0, 120, "12-5", "es"),
 ("Conejo (cocinado)", P, 173, 33, 0, 3.5, 0, 120, "", "cat"), ("Pollo de corral (cocinado)", P, 190, 27, 0, 9, 0, 150, "", "cat"), ("Presa de cerdo ibérico (cocinada)", P, 270, 28, 0, 17, 0, 120, "", "es"),
 ("Magret de pato (cocinado)", P, 190, 27, 0, 9, 0, 120, "", "es"), ("Costillas de cerdo (cocinadas)", P, 290, 24, 0, 21, 0, 150, "", "es"), ("Morcillo de ternera (hervido)", P, 190, 29, 0, 8, 0, 100, "10-4", "es"),
 # quesos y lácteos
 ("Queso manchego curado", L, 430, 30, 0.5, 34, 0, 30, "", "es"), ("Queso manchego semicurado", L, 390, 26, 0.5, 31, 0, 30, "", "es"), ("Queso Mahón", L, 360, 25, 1, 28, 0, 30, "", "es"),
 ("Queso Idiazábal", L, 395, 27, 1, 32, 0, 30, "", "es"), ("Queso Cabrales", L, 380, 21, 1, 32, 0, 30, "", "es"), ("Queso de Tetilla", L, 330, 20, 1, 27, 0, 30, "", "es"),
 ("Queso Garrotxa", L, 360, 22, 1, 29, 0, 30, "", "cat"), ("Queso de cabra", L, 270, 17, 1, 22, 0, 40, "", "es"), ("Mató (queso fresco)", L, 125, 9, 3, 8.5, 0, 60, "", "cat"),
 ("Cuajada", L, 90, 5, 5, 5.5, 0, 125, "", "es"), ("Leche de oveja", L, 92, 5.5, 4.8, 6.5, 0, 200, "", "es"), ("Leche de cabra", L, 69, 3.6, 4.5, 4.1, 0, 200, "", "es"),
 # cereales y tubérculos
 ("Pa de pagès (pan de payés)", C, 260, 8, 52, 1.2, 2.5, 40, "", "cat"), ("Arroz bomba / del Delta (crudo)", C, 355, 7, 79, 0.6, 1, 70, "", "cat"), ("Arroz de Calasparra (crudo)", C, 355, 7, 79, 0.6, 1, 70, "", "es"),
 ("Harina de trigo", C, 364, 10, 76, 1, 2.7, 10, "", "es"), ("Fideos (crudos)", C, 360, 12, 72, 1.5, 3, 70, "", "cat"), ("Harina de garbanzo", C, 387, 22, 58, 7, 10, 10, "", "es"), ("Patata de Prades (cruda)", C, 77, 2, 17, 0.1, 2, 200, "9-11", "cat"),
 ("Moniato asado", C, 110, 1.6, 26, 0.1, 3, 150, "10-12", "cat"),
 # legumbres
 ("Mongeta del ganxet (cocida)", LEG, 120, 8, 20, 0.5, 6, 200, "", "cat"), ("Lenteja pardina (cocida)", LEG, 116, 9, 20, 0.4, 7.9, 200, "", "es"), ("Fabes asturianas (cocidas)", LEG, 130, 8.5, 23, 0.6, 6, 200, "", "es"),
 ("Alubia roja de Tolosa (cocida)", LEG, 127, 9, 22, 0.5, 6, 200, "", "es"), ("Judiones de La Granja (cocidos)", LEG, 130, 8.5, 23, 0.5, 6, 200, "", "es"), ("Altramuces (tramusos)", LEG, 120, 16, 10, 3, 5, 50, "", "es"),
 ("Garbanzos de cocido (secos, sin cocer)", LEG, 364, 20, 61, 6, 17, 60, "", "es"),
 # verduras
 ("Calçots", V, 35, 1.5, 7.5, 0.2, 2, 150, "12-3", "cat"), ("Alcachofa", V, 47, 3.3, 10.5, 0.2, 5.4, 120, "11-5", "cat"), ("Espárrago triguero", V, 24, 2.5, 3.5, 0.2, 2, 100, "3-6", "es"),
 ("Espárrago blanco (conserva)", V, 20, 2, 2, 0.2, 1, 100, "", "es"), ("Habas tiernas", V, 72, 6, 10, 0.5, 5, 100, "3-6", "cat"), ("Tirabeques", V, 42, 2.8, 7.5, 0.2, 2.5, 100, "3-6", "es"),
 ("Pimiento del piquillo (conserva)", V, 30, 1, 6, 0.3, 2, 50, "", "es"), ("Pimiento de Padrón", V, 28, 1.3, 5, 0.3, 2, 100, "5-10", "es"), ("Pimiento verde", V, 20, 0.9, 4.6, 0.2, 1.7, 120, "5-10", "es"),
 ("Tomate de colgar (tomàquet de penjar)", V, 20, 1, 4, 0.2, 1, 100, "", "cat"), ("Cebolla dulce (Figueres / Fuentes)", V, 36, 1, 8.5, 0.1, 1.6, 100, "6-9", "cat"), ("Cebolleta", V, 30, 1.3, 7, 0.2, 1.8, 50, "4-7", "es"),
 ("Puerro", V, 31, 1.8, 7, 0.3, 2, 100, "10-4", "es"), ("Acelga", V, 19, 1.8, 3.7, 0.2, 1.6, 100, "10-5", "es"), ("Cardo", V, 20, 0.7, 4.5, 0.1, 1.6, 150, "11-2", "es"),
 ("Borraja", V, 21, 1.8, 3.4, 0.7, 1, 150, "10-3", "es"), ("Nabo", V, 28, 0.9, 6.4, 0.1, 1.8, 100, "10-3", "cat"), ("Remolacha", V, 43, 1.6, 10, 0.2, 2.8, 100, "10-4", "es"),
 ("Rábano", V, 16, 0.7, 3.4, 0.1, 1.6, 50, "3-6", "es"), ("Apio", V, 16, 0.7, 3, 0.2, 1.6, 60, "10-4", "es"), ("Hinojo", V, 31, 1.2, 7.3, 0.2, 3.1, 150, "10-4", "es"),
 ("Endibia", V, 17, 1, 3.4, 0.1, 3, 100, "10-4", "es"), ("Escarola", V, 17, 1.3, 3.4, 0.2, 3.1, 80, "10-3", "cat"), ("Canónigos", V, 21, 2, 3.6, 0.4, 1.6, 50, "10-3", "es"),
 ("Cogollos de Tudela", V, 15, 1.4, 2.2, 0.2, 1.2, 60, "11-4", "es"), ("Rúcula", V, 25, 2.6, 3.7, 0.7, 1.6, 30, "3-11", "es"), ("Lombarda", V, 31, 1.4, 7.4, 0.2, 2.1, 100, "10-3", "es"),
 ("Coles de Bruselas", V, 43, 3.4, 9, 0.3, 3.8, 100, "11-2", "es"), ("Col rizada (kale)", V, 49, 4.3, 8.8, 0.9, 3.6, 60, "11-3", "es"), ("Chirivía", V, 75, 1.2, 18, 0.3, 5, 100, "10-3", "es"),
 ("Ajo tierno", V, 40, 2.5, 8, 0.2, 2, 30, "3-6", "es"), ("Rovellón / níscalo", V, 30, 2.5, 4, 0.5, 2, 100, "9-11", "cat"), ("Boletus edulis (cep)", V, 34, 3.7, 5, 0.4, 2.5, 100, "9-11", "cat"),
 ("Rossinyol / rebozuelo", V, 32, 1.5, 6, 0.5, 5, 100, "9-11", "cat"), ("Seta de cardo", V, 33, 3.3, 6, 0.4, 2.5, 100, "10-12", "es"), ("Trufa negra", V, 25, 3, 2, 0.5, 0, 5, "12-3", "cat"),
 # frutas
 ("Mandarina / clementina", F, 47, 0.8, 12, 0.3, 1.7, 80, "10-2", "es"), ("Limón", F, 29, 1.1, 9, 0.3, 2.8, 60, "10-6", "es"), ("Pomelo", F, 42, 0.8, 11, 0.1, 1.6, 200, "11-4", "es"),
 ("Granada", F, 83, 1.7, 19, 1.2, 4, 150, "9-12", "es"), ("Caqui", F, 70, 0.6, 18, 0.2, 3.6, 150, "10-12", "es"), ("Chirimoya", F, 75, 1.6, 18, 0.7, 3, 200, "10-2", "es"),
 ("Níspero", F, 47, 0.4, 12, 0.2, 1.7, 50, "4-5", "es"), ("Cereza / picota", F, 63, 1.1, 16, 0.2, 2.1, 100, "5-7", "es"), ("Albaricoque", F, 48, 1.4, 11, 0.4, 2, 50, "5-7", "es"),
 ("Ciruela", F, 46, 0.7, 11, 0.3, 1.4, 60, "6-9", "es"), ("Paraguayo", F, 45, 0.9, 11, 0.3, 1.5, 100, "6-9", "cat"), ("Nectarina", F, 44, 1.1, 10.6, 0.3, 1.7, 150, "5-9", "cat"),
 ("Melocotón de Calanda", F, 45, 0.9, 11, 0.3, 1.5, 150, "9-11", "es"), ("Higo", F, 74, 0.8, 19, 0.3, 2.9, 60, "8-10", "cat"), ("Breva", F, 74, 0.8, 19, 0.3, 2.9, 60, "6-7", "es"),
 ("Membrillo", F, 57, 0.4, 15, 0.1, 1.9, 200, "10-12", "es"), ("Frambuesa", F, 52, 1.2, 12, 0.7, 6.5, 100, "6-10", "cat"), ("Mora", F, 43, 1.4, 10, 0.5, 5.3, 100, "7-9", "es"),
 ("Plátano de Canarias", F, 90, 1.1, 22, 0.3, 2.6, 120, "", "es"), ("Pasas de Málaga", F, 299, 3, 79, 0.5, 3.7, 25, "", "es"), ("Orejones de albaricoque", F, 241, 3.4, 63, 0.5, 7.3, 30, "", "es"),
 ("Ciruelas pasas", F, 240, 2.2, 64, 0.4, 7, 30, "", "es"), ("Higos secos", F, 249, 3.3, 64, 0.9, 9.8, 40, "", "es"),
 # frutos secos, aceite y dulces
 ("Avellanas de Reus", N, 628, 15, 17, 61, 10, 25, "", "cat"), ("Almendra Marcona (tostada)", N, 610, 21, 20, 54, 12, 25, "", "es"), ("Piñones", N, 673, 14, 13, 68, 3.7, 15, "", "cat"),
 ("Castañas (asadas)", N, 245, 3.2, 53, 2.2, 5, 60, "10-12", "cat"), ("Aceite de oliva virgen extra (arbequina)", N, 884, 0, 0, 100, 0, 10, "", "cat"),
 ("Aceitunas verdes", N, 145, 1, 3.8, 15, 3.3, 30, "", "es"), ("Aceitunas negras", N, 115, 0.8, 6, 11, 3.2, 30, "", "es"), ("Turrón de Jijona", N, 500, 12, 50, 30, 3, 30, "11-1", "es"),
 ("Turrón de Alicante", N, 480, 14, 50, 27, 3, 30, "11-1", "es"), ("Mazapán", N, 470, 9, 55, 25, 3, 25, "11-1", "es"), ("Polvorón", N, 520, 6, 52, 32, 1.5, 30, "11-1", "es"),
 ("Panellets (piñones)", N, 420, 8, 50, 20, 3, 30, "10-11", "cat"), ("Carne de membrillo", N, 250, 0.3, 63, 0.1, 1, 30, "", "es"), ("Carquinyolis", N, 430, 9, 63, 16, 4, 20, "", "cat"),
 # otros
 ("Pimentón de la Vera", O, 282, 14, 54, 13, 35, 3, "", "es"), ("Azafrán", O, 310, 11, 65, 6, 4, 1, "", "es"), ("Sofrito catalán", O, 85, 1.2, 7, 6, 1.5, 50, "", "cat"),
 ("Romesco", O, 215, 4, 8, 19, 3, 30, "", "cat"), ("Allioli", O, 600, 1, 1, 66, 0, 15, "", "cat"), ("Vinagre de Jerez", O, 20, 0, 0.5, 0, 0, 10, "", "es"),
 ("Caldo de verduras", O, 6, 0.2, 1, 0.1, 0, 250, "", "es"), ("Caldo de pollo / carne", O, 10, 1, 0.5, 0.4, 0, 250, "", "es"), ("Horchata de chufa", O, 70, 0.5, 14, 1.8, 0.5, 250, "5-9", "es"),
 ("Cava brut", O, 75, 0.3, 1.4, 0, 0, 100, "", "cat"), ("Vermut", O, 150, 0, 15, 0, 0, 70, "", "cat"), ("Sidra", O, 40, 0, 2, 0, 0, 200, "", "es"), ("Vino blanco", O, 82, 0.1, 2.6, 0, 0, 150, "", "es"),
 ("Crema catalana", O, 175, 5, 22, 7, 0, 120, "", "cat"),
]


def months(spec):
    """'11-3' -> [11,12,1,2,3]; '6-9,12' -> [6,7,8,9,12]; '' -> [] (todo el año)."""
    out = []
    for part in str(spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        a, _, b = part.partition("-")
        a = int(a); b = int(b) if b else a
        m = a
        while True:
            out.append(m)
            if m == b:
                break
            m = m % 12 + 1
    return sorted(set(out))
