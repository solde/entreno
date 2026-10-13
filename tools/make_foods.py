#!/usr/bin/env python3
"""Genera data/foods.json: alimentos habituales con valores ORIENTATIVOS por 100 g (tablas tipo USDA/BEDCA, redondeados).
Cada fila: (nombre, categoria, kcal, proteina, hidratos, grasa, fibra, porcion_g). Las porciones son las unidades habituales (1 huevo, 1 manzana…)."""
import json, os, sys
P, L, C, V, F, N, O = "Proteínas", "Lácteos y huevos", "Cereales y tubérculos", "Verduras", "Frutas", "Frutos secos, grasas y dulces", "Otros"
LEG = "Legumbres"
FOODS = [
 # proteinas
 ("Pechuga de pollo (cruda)", P, 120, 22.5, 0, 2.6, 0, 150), ("Pechuga de pollo (cocinada)", P, 165, 31, 0, 3.6, 0, 120), ("Muslo de pollo sin piel (cocinado)", P, 179, 24.5, 0, 8.2, 0, 100),
 ("Pechuga de pavo (cocinada)", P, 135, 30, 0, 1, 0, 100), ("Ternera magra (cocinada)", P, 217, 26, 0, 12, 0, 120), ("Solomillo de cerdo (cocinado)", P, 143, 26, 0, 3.5, 0, 120),
 ("Jamón serrano", P, 241, 30, 0.1, 13, 0, 30), ("Jamón cocido", P, 107, 17, 1.5, 3.5, 0, 30), ("Salmón (cocinado)", P, 206, 22, 0, 12.4, 0, 120), ("Atún al natural (lata, escurrido)", P, 116, 25.5, 0, 0.8, 0, 80),
 ("Atún en aceite (lata, escurrido)", P, 198, 29, 0, 8.2, 0, 80), ("Merluza (cruda)", P, 80, 17, 0, 1, 0, 150), ("Bacalao (cocinado)", P, 105, 23, 0, 0.9, 0, 150), ("Gambas / langostinos (cocidos)", P, 99, 24, 0.2, 0.3, 0, 100),
 ("Sardinas en lata (escurridas)", P, 208, 24.6, 0, 11.5, 0, 90), ("Tofu firme", P, 144, 17, 3, 8.7, 2, 120), ("Tempeh", P, 192, 20, 7.6, 10.8, 0, 100), ("Seitán", P, 370, 75, 14, 1.9, 0, 100),
 ("Proteína de suero (whey)", P, 400, 80, 8, 6, 0, 30), ("Huevo entero", L, 143, 12.6, 0.7, 9.5, 0, 55), ("Clara de huevo", L, 52, 10.9, 0.7, 0.2, 0, 33),
 # lacteos
 ("Leche entera", L, 61, 3.2, 4.8, 3.3, 0, 250), ("Leche semidesnatada", L, 46, 3.4, 4.8, 1.6, 0, 250), ("Leche desnatada", L, 34, 3.4, 5, 0.1, 0, 250), ("Yogur natural", L, 61, 3.5, 4.7, 3.3, 0, 125),
 ("Yogur griego natural", L, 97, 9, 4, 5, 0, 125), ("Yogur griego 0 %", L, 59, 10.2, 3.6, 0.4, 0, 125), ("Queso fresco batido 0 %", L, 45, 8, 3.5, 0.2, 0, 125), ("Requesón / cottage", L, 98, 11, 3.4, 4.3, 0, 100),
 ("Queso mozzarella", L, 280, 22, 2.2, 22, 0, 30), ("Queso curado", L, 392, 25, 0.5, 32, 0, 30), ("Queso fresco (tipo Burgos)", L, 174, 12, 3.3, 12, 0, 60), ("Mantequilla", N, 717, 0.9, 0.1, 81, 0, 10),
 ("Bebida de soja (sin azúcar)", L, 33, 2.9, 0.4, 1.8, 0.4, 250), ("Bebida de avena", L, 45, 1, 9, 1, 0.8, 250), ("Bebida de almendras (sin azúcar)", L, 15, 0.5, 0.3, 1.1, 0.2, 250),
 # cereales
 ("Arroz blanco (crudo)", C, 365, 7.1, 80, 0.7, 1.3, 70), ("Arroz blanco (cocido)", C, 130, 2.7, 28, 0.3, 0.4, 180), ("Arroz integral (cocido)", C, 123, 2.7, 25.6, 1, 1.6, 180), ("Pasta (cruda)", C, 371, 13, 75, 1.5, 3, 80),
 ("Pasta (cocida)", C, 158, 5.8, 31, 0.9, 1.8, 200), ("Pan blanco", C, 265, 9, 49, 3.2, 2.7, 40), ("Pan integral", C, 247, 13, 41, 3.4, 7, 40), ("Copos de avena", C, 389, 16.9, 66, 6.9, 10.6, 40),
 ("Quinoa (cocida)", C, 120, 4.4, 21.3, 1.9, 2.8, 180), ("Cuscús (cocido)", C, 112, 3.8, 23.2, 0.2, 1.4, 180), ("Patata (cocida)", C, 87, 1.9, 20, 0.1, 1.8, 200), ("Patata (cruda)", C, 77, 2, 17, 0.1, 2.2, 200),
 ("Boniato (cocido)", C, 90, 2, 21, 0.15, 3.3, 200), ("Tortilla de trigo", C, 310, 8, 50, 8, 2.5, 45), ("Cereales de desayuno (copos de maíz)", C, 357, 7.5, 84, 0.4, 3, 30), ("Galletas María", C, 440, 7, 75, 12, 2, 20),
 # legumbres
 ("Lentejas (cocidas)", LEG, 116, 9, 20, 0.4, 7.9, 200), ("Garbanzos (cocidos)", LEG, 164, 8.9, 27.4, 2.6, 7.6, 200), ("Alubias blancas (cocidas)", LEG, 139, 9.7, 25, 0.5, 6.3, 200), ("Judías negras (cocidas)", LEG, 132, 8.9, 23.7, 0.5, 8.7, 200),
 ("Edamame", LEG, 121, 11.9, 8.9, 5.2, 5.2, 100), ("Hummus", O, 166, 8, 14, 9.6, 6, 50),
 # verduras
 ("Brócoli", V, 34, 2.8, 6.6, 0.4, 2.6, 150), ("Coliflor", V, 25, 1.9, 5, 0.3, 2, 150), ("Espinacas", V, 23, 2.9, 3.6, 0.4, 2.2, 100), ("Lechuga", V, 15, 1.4, 2.9, 0.2, 1.3, 80), ("Tomate", V, 18, 0.9, 3.9, 0.2, 1.2, 150),
 ("Pepino", V, 15, 0.7, 3.6, 0.1, 0.5, 150), ("Zanahoria", V, 41, 0.9, 9.6, 0.2, 2.8, 80), ("Pimiento rojo", V, 31, 1, 6, 0.3, 2.1, 120), ("Cebolla", V, 40, 1.1, 9.3, 0.1, 1.7, 80), ("Calabacín", V, 17, 1.2, 3.1, 0.3, 1, 200),
 ("Berenjena", V, 25, 1, 6, 0.2, 3, 200), ("Judías verdes", V, 31, 1.8, 7, 0.2, 2.7, 150), ("Champiñones", V, 22, 3.1, 3.3, 0.3, 1, 100), ("Ajo", V, 149, 6.4, 33, 0.5, 2.1, 5), ("Aguacate", V, 160, 2, 8.5, 14.7, 6.7, 100),
 ("Calabaza", V, 26, 1, 6.5, 0.1, 0.5, 150), ("Espárragos", V, 20, 2.2, 3.9, 0.1, 2.1, 100), ("Repollo / col", V, 25, 1.3, 5.8, 0.1, 2.5, 100), ("Guisantes", V, 81, 5.4, 14.5, 0.4, 5.1, 100), ("Maíz dulce (lata)", V, 81, 2.5, 17, 1, 2.4, 80),
 # frutas
 ("Plátano", F, 89, 1.1, 22.8, 0.3, 2.6, 120), ("Manzana", F, 52, 0.3, 13.8, 0.2, 2.4, 180), ("Naranja", F, 47, 0.9, 11.8, 0.1, 2.4, 180), ("Fresas", F, 32, 0.7, 7.7, 0.3, 2, 150), ("Arándanos", F, 57, 0.7, 14.5, 0.3, 2.4, 100),
 ("Uvas", F, 69, 0.7, 18, 0.2, 0.9, 120), ("Pera", F, 57, 0.4, 15, 0.1, 3.1, 180), ("Kiwi", F, 61, 1.1, 14.7, 0.5, 3, 80), ("Melón", F, 34, 0.8, 8.2, 0.2, 0.9, 200), ("Sandía", F, 30, 0.6, 7.6, 0.2, 0.4, 250),
 ("Piña", F, 50, 0.5, 13, 0.1, 1.4, 150), ("Mango", F, 60, 0.8, 15, 0.4, 1.6, 150), ("Melocotón", F, 39, 0.9, 9.5, 0.3, 1.5, 150), ("Dátiles", F, 277, 1.8, 75, 0.2, 6.7, 25),
 # frutos secos, grasas y dulces
 ("Almendras", N, 579, 21, 22, 50, 12.5, 25), ("Nueces", N, 654, 15, 14, 65, 6.7, 25), ("Cacahuetes", N, 567, 26, 16, 49, 8.5, 25), ("Crema de cacahuete", N, 588, 25, 20, 50, 6, 15),
 ("Semillas de chía", N, 486, 17, 42, 31, 34, 15), ("Semillas de lino", N, 534, 18, 29, 42, 27, 10), ("Pipas de girasol", N, 584, 21, 20, 51, 8.6, 25), ("Aceite de oliva", N, 884, 0, 0, 100, 0, 10),
 ("Chocolate negro 70 %", N, 598, 7.8, 46, 43, 11, 20), ("Miel", N, 304, 0.3, 82, 0, 0.2, 15), ("Azúcar", N, 387, 0, 100, 0, 0, 5), ("Mermelada", N, 250, 0.4, 65, 0.1, 1, 20),
 # otros
 ("Tomate frito (salsa)", O, 80, 1.5, 10, 3.5, 1.5, 50), ("Café solo", O, 2, 0.1, 0, 0, 0, 50), ("Cerveza", O, 43, 0.5, 3.6, 0, 0, 330), ("Vino tinto", O, 85, 0.1, 2.6, 0, 0, 150),
]
def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import local_foods as lf
    out = []
    for i, (n, c, k, p, h, g, f, s) in enumerate(FOODS):
        out.append({"id": "f_%03d" % (i + 1), "name": n, "category": c, "kcal": k, "protein": p, "carbs": h, "fat": g, "fiber": f, "serving_g": s,
                    "months": lf.months(lf.SEASON_EXISTING.get(n, "")), "origin": lf.ORIGIN_EXISTING.get(n, "")})
    names = {x["name"] for x in out}
    for j, (n, c, k, p, h, g, f, s, mo, org) in enumerate(lf.LOCAL):
        assert n not in names, "duplicado: " + n
        out.append({"id": "f_%03d" % (len(FOODS) + j + 1), "name": n, "category": c, "kcal": k, "protein": p, "carbs": h, "fat": g, "fiber": f, "serving_g": s, "months": lf.months(mo), "origin": org})
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "foods.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(len(out), "alimentos")
if __name__ == "__main__":
    main()
