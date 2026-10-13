#!/usr/bin/env python3
"""Genera data/recipes.json: recetas tradicionales de España y Cataluña con su época ideal. Ingredientes = nombre EXACTO de data/foods.json y gramos del TOTAL de la receta.
Cada receta: (uid, nombre, raciones, minutos, meses, origen, tipo, [(alimento, g)], pasos, nota)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_foods import months

R = [
 # ---- verano
 ("gazpacho", "Gazpacho andaluz", 4, 15, "5-9", "es", "Plato frío", [("Tomate", 1000), ("Pepino", 200), ("Pimiento verde", 150), ("Ajo", 5), ("Pan blanco", 60), ("Aceite de oliva", 50), ("Vinagre de Jerez", 20)],
  "1. Trocea las verduras y remoja el pan en agua.\n2. Tritura todo con el aceite, el vinagre y sal hasta que quede fino.\n3. Cuela si quieres textura sedosa y enfría al menos 2 horas.", "Sirve muy frío, con un chorrito de aceite."),
 ("salmorejo", "Salmorejo cordobés", 4, 15, "5-9", "es", "Plato frío", [("Tomate", 1000), ("Pan blanco", 200), ("Aceite de oliva", 100), ("Ajo", 5), ("Vinagre de Jerez", 15), ("Huevo entero", 110), ("Jamón serrano", 40)],
  "1. Cuece los huevos 10 min y pícalos.\n2. Tritura el tomate con el pan, el ajo y la sal; añade el aceite en hilo hasta emulsionar.\n3. Enfría y sirve con el huevo y el jamón picados.", ""),
 ("ajoblanco", "Ajoblanco malagueño con uvas", 4, 15, "5-9", "es", "Plato frío", [("Almendra Marcona (tostada)", 100), ("Pan blanco", 80), ("Ajo", 10), ("Aceite de oliva", 60), ("Vinagre de Jerez", 15), ("Uvas", 150)],
  "1. Remoja el pan 10 min y escúrrelo.\n2. Tritura las almendras con el pan, el ajo, la sal, el aceite, el vinagre y agua fría hasta una crema fina.\n3. Enfría y sirve con las uvas peladas.", ""),
 ("esqueixada", "Esqueixada de bacalao", 4, 15, "5-9", "cat", "Plato frío", [("Bacalao salado (desalado, crudo)", 300), ("Tomate", 300), ("Cebolla dulce (Figueres / Fuentes)", 80), ("Aceitunas negras", 40), ("Aceite de oliva virgen extra (arbequina)", 30)],
  "1. Desmenuza el bacalao desalado en tiras.\n2. Corta el tomate y la cebolla en tiras finas y mézclalo todo con las aceitunas.\n3. Aliña con el aceite y reposa 15 min en frío.", "Pide desalar el bacalao 24–48 h antes."),
 ("escalivada", "Escalivada con anchoas", 3, 60, "6-10", "cat", "Verduras al horno", [("Pimiento rojo", 300), ("Berenjena", 400), ("Cebolla", 150), ("Aceite de oliva virgen extra (arbequina)", 30), ("Anchoas (L'Escala, en aceite, escurridas)", 40)],
  "1. Asa las verduras enteras al horno a 200 °C unos 50 min.\n2. Déjalas templar tapadas, pélalas y córtalas en tiras.\n3. Aliña con aceite y sal y corona con las anchoas.", "Con pa de pagès es una cena completa."),
 ("pisto", "Pisto con huevo", 3, 40, "6-10", "es", "Verduras salteadas", [("Calabacín", 300), ("Pimiento verde", 150), ("Tomate", 400), ("Cebolla", 150), ("Aceite de oliva", 40), ("Huevo entero", 110)],
  "1. Sofríe la cebolla y el pimiento picados 10 min.\n2. Añade el calabacín y, después, el tomate; cocina a fuego suave 20 min.\n3. Sirve con el huevo frito o poché encima.", ""),
 ("samfaina", "Samfaina", 4, 45, "6-10", "cat", "Verduras salteadas", [("Berenjena", 300), ("Calabacín", 300), ("Pimiento rojo", 200), ("Cebolla", 150), ("Tomate", 300), ("Aceite de oliva virgen extra (arbequina)", 40)],
  "1. Sofríe la cebolla; añade el pimiento y la berenjena en dados.\n2. Suma el calabacín y, al final, el tomate rallado.\n3. Cocina a fuego lento 25 min hasta que quede jugosa.", "Acompaña pollo, bacalao o huevos."),
 ("tumbet", "Tumbet mallorquín", 4, 60, "6-10", "es", "Verduras al horno", [("Patata (cruda)", 400), ("Berenjena", 300), ("Pimiento rojo", 200), ("Tomate", 300), ("Aceite de oliva", 60)],
  "1. Fríe o asa por separado la patata, la berenjena y el pimiento en rodajas.\n2. Haz una salsa de tomate con un poco de aceite.\n3. Monta capas de patata, berenjena y pimiento y cubre con la salsa.", ""),
 ("ensaladilla", "Ensaladilla rusa", 4, 40, "5-9", "es", "Plato frío", [("Patata (cruda)", 400), ("Zanahoria", 100), ("Guisantes", 100), ("Huevo entero", 165), ("Atún en aceite (lata, escurrido)", 100), ("Allioli", 40)],
  "1. Cuece patata, zanahoria, guisantes y huevos; deja enfriar.\n2. Corta todo en dados pequeños.\n3. Mezcla con el atún y el allioli y enfría 1 hora.", ""),
 ("ensalada-tomate-atun", "Ensalada de tomate, cebolla dulce y atún", 2, 10, "6-9", "es", "Plato frío", [("Tomate", 400), ("Cebolla dulce (Figueres / Fuentes)", 100), ("Atún en aceite (lata, escurrido)", 100), ("Aceitunas negras", 30), ("Aceite de oliva virgen extra (arbequina)", 20)],
  "1. Corta el tomate en gajos y la cebolla en pluma.\n2. Añade el atún y las aceitunas.\n3. Aliña con aceite y sal en escamas.", "Mejor con tomate maduro de temporada."),
 ("sardinas-plancha", "Sardinas a la plancha con ensalada", 2, 15, "5-10", "es", "Pescado a la plancha", [("Sardina fresca", 400), ("Tomate", 200), ("Lechuga", 100), ("Aceite de oliva", 15), ("Limón", 30)],
  "1. Seca las sardinas, salpimenta y ponlas en plancha muy caliente 2–3 min por lado.\n2. Prepara la ensalada de tomate y lechuga.\n3. Sirve con limón y un hilo de aceite.", ""),
 ("sopa-melon", "Crema fría de melón con jamón", 4, 10, "6-9", "es", "Plato frío", [("Melón", 600), ("Jamón serrano", 40), ("Aceite de oliva", 20)],
  "1. Tritura el melón bien frío con el aceite y una pizca de sal.\n2. Sirve en cuencos con el jamón en virutas.", ""),
 ("yogur-fruta-verano", "Yogur con melocotón, almendras y miel", 2, 5, "6-9", "es", "Desayuno / postre", [("Yogur natural", 250), ("Melocotón", 150), ("Miel", 10), ("Almendras", 20)],
  "1. Pela y corta el melocotón.\n2. Sirve sobre el yogur con las almendras laminadas y la miel.", ""),
 ("higos-jamon", "Higos con jamón y queso de cabra", 4, 10, "8-10", "cat", "Entrante", [("Higo", 300), ("Jamón ibérico de bellota", 60), ("Queso de cabra", 80), ("Miel", 10)],
  "1. Abre los higos en cruz.\n2. Rellénalos con queso de cabra y envuélvelos con jamón.\n3. Termina con un hilo de miel.", ""),
 ("pa-amb-tomaquet", "Pa amb tomàquet con jamón", 2, 10, "", "cat", "Desayuno / merienda", [("Pa de pagès (pan de payés)", 160), ("Tomate", 150), ("Aceite de oliva virgen extra (arbequina)", 20), ("Jamón ibérico de bellota", 60)],
  "1. Tuesta el pan.\n2. Frota con tomate maduro, añade el aceite y la sal.\n3. Sirve con el jamón.", ""),
 ("pollo-samfaina", "Pollo con samfaina", 4, 50, "6-10", "cat", "Plato de carne", [("Muslo de pollo sin piel (cocinado)", 600), ("Berenjena", 200), ("Calabacín", 150), ("Pimiento rojo", 150), ("Cebolla", 100), ("Tomate", 200), ("Aceite de oliva", 40)],
  "1. Dora el pollo troceado y resérvalo.\n2. Sofríe las verduras en dados y añade el tomate.\n3. Vuelve a poner el pollo y cuece tapado 25 min.", ""),
 ("tortilla-calabacin", "Tortilla de calabacín", 3, 25, "5-10", "es", "Plato ligero", [("Calabacín", 400), ("Huevo entero", 330), ("Cebolla", 80), ("Aceite de oliva", 20)],
  "1. Pocha la cebolla y el calabacín en láminas.\n2. Mezcla con los huevos batidos.\n3. Cuaja la tortilla en sartén por ambos lados.", ""),
 # ---- primavera
 ("faves-catalana", "Faves a la catalana", 4, 40, "3-5", "cat", "Plato de cuchara", [("Habas tiernas", 800), ("Botifarra negra (cocinada)", 150), ("Jamón serrano", 60), ("Cebolla", 100), ("Ajo", 10), ("Aceite de oliva", 20), ("Vino blanco", 50)],
  "1. Sofríe la cebolla, el ajo, el jamón y la butifarra en trozos.\n2. Añade las habas y el vino y deja reducir.\n3. Cubre con agua o caldo y cuece 25 min.", "Las habas jóvenes son lo mejor de marzo a mayo."),
 ("guisantes-jamon", "Guisantes con jamón", 4, 25, "3-6", "es", "Verduras salteadas", [("Guisantes", 600), ("Jamón serrano", 60), ("Cebolleta", 100), ("Aceite de oliva", 20), ("Caldo de verduras", 100)],
  "1. Pocha la cebolleta y dora el jamón.\n2. Añade los guisantes y el caldo.\n3. Cuece 12–15 min a fuego suave.", ""),
 ("esparragos-huevo", "Espárragos trigueros con huevo", 2, 15, "3-6", "es", "Plato ligero", [("Espárrago triguero", 400), ("Huevo entero", 220), ("Aceite de oliva", 20)],
  "1. Saltea los espárragos en aceite 5 min.\n2. Haz huevos poché o fritos.\n3. Sirve los espárragos con el huevo encima.", ""),
 ("revuelto-ajetes", "Revuelto de ajetes y gambas", 2, 15, "3-6", "es", "Plato ligero", [("Ajo tierno", 100), ("Huevo entero", 220), ("Gambas / langostinos (cocidos)", 150), ("Aceite de oliva", 15)],
  "1. Saltea los ajetes troceados 4 min.\n2. Añade las gambas y, al final, los huevos batidos.\n3. Remueve a fuego suave hasta que cuajen cremosos.", ""),
 ("ensalada-fresas", "Ensalada de espinacas, fresas y queso de cabra", 2, 10, "3-6", "es", "Plato ligero", [("Espinacas", 100), ("Fresas", 200), ("Queso de cabra", 80), ("Nueces", 30), ("Aceite de oliva virgen extra (arbequina)", 15)],
  "1. Lava las espinacas y corta las fresas.\n2. Añade el queso desmenuzado y las nueces.\n3. Aliña con aceite, sal y unas gotas de vinagre.", ""),
 ("crema-guisantes", "Crema de guisantes y cebolleta", 4, 25, "3-6", "es", "Cremas y sopas", [("Guisantes", 500), ("Patata (cruda)", 150), ("Cebolleta", 100), ("Aceite de oliva", 15), ("Caldo de verduras", 400)],
  "1. Pocha la cebolleta y la patata en dados.\n2. Añade los guisantes y el caldo y cuece 15 min.\n3. Tritura fino y rectifica de sal.", ""),
 ("alcachofas-jamon", "Alcachofas a la plancha con jamón", 4, 25, "11-5", "cat", "Verduras salteadas", [("Alcachofa", 600), ("Jamón serrano", 60), ("Aceite de oliva", 25), ("Ajo", 10)],
  "1. Limpia las alcachofas y cuécelas 8 min en agua con limón.\n2. Dóralas en plancha con ajo y aceite.\n3. Sirve con el jamón.", ""),
 ("torrijas", "Torrijas", 4, 30, "3-4", "es", "Postre", [("Pan blanco", 250), ("Leche entera", 500), ("Huevo entero", 110), ("Azúcar", 40), ("Aceite de oliva", 40)],
  "1. Empapa las rebanadas en leche con un poco de azúcar.\n2. Pásalas por huevo batido y fríelas hasta dorar.\n3. Espolvorea con azúcar y canela.", "Típicas de Semana Santa."),
 ("cordero-patatas", "Cordero asado con patatas", 4, 120, "12-5", "es", "Plato de horno", [("Cordero lechal (asado)", 600), ("Patata (cruda)", 600), ("Ajo", 15), ("Aceite de oliva", 30), ("Vino blanco", 100)],
  "1. Sazona el cordero con ajo y sal y ponlo en la bandeja con las patatas.\n2. Riega con vino y aceite.\n3. Hornea a 180 °C unas 2 horas, dándole la vuelta a media cocción.", ""),
 # ---- otoño
 ("crema-calabaza", "Crema de calabaza", 4, 30, "9-12", "es", "Cremas y sopas", [("Calabaza", 800), ("Cebolla", 100), ("Zanahoria", 100), ("Aceite de oliva", 20), ("Caldo de verduras", 400)],
  "1. Pocha la cebolla y la zanahoria.\n2. Añade la calabaza en dados y el caldo y cuece 20 min.\n3. Tritura y ajusta la textura.", ""),
 ("arroz-setas", "Arroz meloso de setas", 4, 40, "9-11", "cat", "Arroces", [("Arroz bomba / del Delta (crudo)", 280), ("Rovellón / níscalo", 200), ("Boletus edulis (cep)", 150), ("Cebolla", 100), ("Ajo", 10), ("Caldo de verduras", 800), ("Aceite de oliva virgen extra (arbequina)", 30)],
  "1. Saltea las setas a fuego fuerte y resérvalas.\n2. Sofríe cebolla y ajo, nacara el arroz y añade el caldo caliente.\n3. Cuece 17 min, incorpora las setas y deja reposar 3 min.", ""),
 ("fricando", "Fricandó con rovellons", 4, 90, "10-11", "cat", "Plato de cuchara", [("Morcillo de ternera (hervido)", 600), ("Rovellón / níscalo", 300), ("Cebolla", 150), ("Tomate", 150), ("Aceite de oliva", 40), ("Vino blanco", 100)],
  "1. Dora la carne en láminas y resérvala.\n2. Sofríe la cebolla y el tomate; añade el vino.\n3. Vuelve a poner la carne con agua y cuece 45 min; añade las setas los últimos 15.", ""),
 ("mongetes-botifarra", "Mongetes del ganxet con butifarra", 4, 20, "10-3", "cat", "Plato de cuchara", [("Mongeta del ganxet (cocida)", 600), ("Botifarra blanca (cocinada)", 300), ("Aceite de oliva", 20), ("Ajo", 10)],
  "1. Dora la butifarra a la plancha.\n2. Saltea las mongetes cocidas con ajo.\n3. Sirve junto.", "Clásico de tardes frías de otoño e invierno."),
 ("revuelto-setas", "Revuelto de setas", 2, 15, "9-12", "es", "Plato ligero", [("Seta de cardo", 250), ("Huevo entero", 220), ("Ajo", 10), ("Aceite de oliva", 20)],
  "1. Saltea las setas con ajo hasta que suelten el agua.\n2. Añade los huevos batidos y remueve a fuego suave.", ""),
 ("castanyada", "Castañas, moniato y panellets", 4, 40, "10-11", "cat", "Merienda", [("Castañas (asadas)", 200), ("Moniato asado", 300), ("Panellets (piñones)", 100)],
  "1. Haz un corte a las castañas y ásalas 25 min a 220 °C.\n2. Asa el moniato 40 min.\n3. Sirve con los panellets.", "Merienda de la Castanyada (1 de noviembre)."),
 ("manzana-asada", "Manzana asada con miel y nueces", 4, 35, "10-2", "es", "Postre", [("Manzana", 600), ("Miel", 30), ("Nueces", 40)],
  "1. Descorazona las manzanas.\n2. Rellénalas con nueces y miel.\n3. Hornea a 180 °C 30 min.", ""),
 ("membrillo-queso", "Membrillo con queso manchego y nueces", 2, 5, "10-12", "es", "Postre", [("Carne de membrillo", 80), ("Queso manchego curado", 80), ("Nueces", 20)],
  "1. Corta el membrillo y el queso en lonchas.\n2. Sirve juntos con las nueces.", ""),
 ("sopa-ajo", "Sopa de ajo castellana", 4, 25, "11-3", "es", "Cremas y sopas", [("Pan blanco", 120), ("Ajo", 20), ("Pimentón de la Vera", 3), ("Huevo entero", 220), ("Aceite de oliva", 40), ("Caldo de pollo / carne", 800)],
  "1. Dora el ajo laminado y el pan en el aceite.\n2. Añade el pimentón y el caldo y cuece 10 min.\n3. Escalfa los huevos en la sopa.", ""),
 # ---- invierno
 ("escudella", "Escudella i carn d'olla", 6, 150, "11-3", "cat", "Plato de cuchara", [("Garbanzos de cocido (secos, sin cocer)", 200), ("Morcillo de ternera (hervido)", 400), ("Botifarra blanca (cocinada)", 150), ("Botifarra negra (cocinada)", 100), ("Patata (cruda)", 300), ("Zanahoria", 150), ("Nabo", 150), ("Puerro", 100), ("Apio", 60), ("Repollo / col", 200), ("Fideos (crudos)", 100)],
  "1. Pon a cocer los garbanzos remojados con la carne y las butifarras en agua fría.\n2. Añade las verduras y cuece 1,5 h espumando.\n3. Cuela el caldo y cuece en él la pasta: es la escudella; sirve aparte la carn d'olla.", "Plato tradicional de Navidad (Sant Esteve) y del invierno catalán."),
 ("cocido", "Cocido madrileño", 5, 180, "11-3", "es", "Plato de cuchara", [("Garbanzos (cocidos)", 400), ("Morcillo de ternera (hervido)", 400), ("Muslo de pollo sin piel (cocinado)", 300), ("Chorizo", 100), ("Morcilla de cebolla", 100), ("Patata (cruda)", 300), ("Zanahoria", 150), ("Repollo / col", 400)],
  "1. Cuece la carne y los garbanzos 1,5 h.\n2. Añade el chorizo, la morcilla y las verduras en la última hora.\n3. Sirve en tres vuelcos: sopa, garbanzos con verdura y carnes.", ""),
 ("fabada", "Fabada asturiana", 4, 150, "11-3", "es", "Plato de cuchara", [("Fabes asturianas (cocidas)", 800), ("Chorizo", 150), ("Morcilla de cebolla", 150), ("Jamón serrano", 80)],
  "1. Cuece las fabes con el chorizo, la morcilla y el jamón en agua fría a fuego suave 2 h.\n2. Asusta (añade agua fría) un par de veces.\n3. Reposa 20 min antes de servir.", ""),
 ("lentejas", "Lentejas estofadas con verduras", 4, 40, "10-3", "es", "Plato de cuchara", [("Lenteja pardina (cocida)", 600), ("Zanahoria", 100), ("Cebolla", 100), ("Pimiento verde", 80), ("Chorizo", 60), ("Patata (cruda)", 150), ("Aceite de oliva", 20), ("Pimentón de la Vera", 2)],
  "1. Sofríe cebolla, pimiento y zanahoria.\n2. Añade el pimentón, las lentejas, la patata y el chorizo con agua.\n3. Cuece 25 min.", ""),
 ("calcotada", "Calçotada con salsa romesco", 4, 45, "12-3", "cat", "Plato típico", [("Calçots", 1200), ("Romesco", 120), ("Pa de pagès (pan de payés)", 160), ("Botifarra blanca (cocinada)", 300), ("Botifarra negra (cocinada)", 160)],
  "1. Asa los calçots a la brasa o al horno muy fuerte hasta que se ennegrezcan por fuera.\n2. Envuélvelos en papel de periódico 15 min.\n3. Pela y moja en el romesco; termina con las butifarras a la brasa.", "Típica de enero a marzo."),
 ("crema-coliflor", "Crema de coliflor y almendra", 4, 30, "10-3", "es", "Cremas y sopas", [("Coliflor", 600), ("Patata (cruda)", 200), ("Cebolla", 100), ("Almendras", 30), ("Aceite de oliva", 20), ("Caldo de verduras", 400)],
  "1. Pocha la cebolla.\n2. Añade coliflor, patata y caldo y cuece 20 min.\n3. Tritura con las almendras.", ""),
 ("crema-puerros", "Crema de puerros y patata", 4, 30, "10-4", "es", "Cremas y sopas", [("Puerro", 400), ("Patata (cruda)", 300), ("Aceite de oliva", 20), ("Caldo de verduras", 500)],
  "1. Pocha el puerro cortado.\n2. Añade la patata y el caldo y cuece 20 min.\n3. Tritura fino.", ""),
 ("garbanzos-espinacas", "Garbanzos con espinacas", 4, 30, "10-5", "es", "Plato de cuchara", [("Garbanzos (cocidos)", 500), ("Espinacas", 300), ("Ajo", 10), ("Pimentón de la Vera", 2), ("Aceite de oliva", 30), ("Pan blanco", 30)],
  "1. Dora el ajo y el pan en aceite y tritúralos con pimentón y un poco de caldo.\n2. Añade los garbanzos y las espinacas.\n3. Cuece 10 min.", "Típico de Semana Santa."),
 ("espinacas-catalana", "Espinacas a la catalana", 4, 20, "10-5", "cat", "Verduras salteadas", [("Espinacas", 600), ("Pasas de Málaga", 30), ("Piñones", 30), ("Aceite de oliva virgen extra (arbequina)", 20), ("Ajo", 10)],
  "1. Cuece las espinacas 2 min y escúrrelas bien.\n2. Dora los piñones y el ajo, añade las pasas y las espinacas.\n3. Saltea 3 min.", ""),
 ("trinxat", "Trinxat de la Cerdanya", 4, 40, "10-3", "cat", "Plato típico", [("Repollo / col", 500), ("Patata (cruda)", 400), ("Ajo", 10), ("Jamón serrano", 60), ("Aceite de oliva", 20)],
  "1. Cuece la col y la patata.\n2. Machácalas con el ajo dorado.\n3. Forma una torta y dórala en sartén con el jamón.", ""),
 ("canelones", "Canelones de Sant Esteve", 6, 90, "12-1", "cat", "Plato de horno", [("Pasta (cruda)", 250), ("Ternera magra (cocinada)", 250), ("Pechuga de pollo (cocinada)", 150), ("Leche entera", 500), ("Harina de trigo", 40), ("Cebolla", 100), ("Queso curado", 40), ("Aceite de oliva", 30)],
  "1. Sofríe la cebolla y las carnes; pícalas finas.\n2. Cuece las placas, rellénalas y enróllalas.\n3. Cubre con bechamel y queso y gratina al horno 15 min.", "Plato de Navidad (Sant Esteve)."),
 ("coliflor-horno", "Coliflor y brócoli al horno con queso", 3, 35, "10-3", "es", "Plato de horno", [("Coliflor", 400), ("Brócoli", 300), ("Queso curado", 60), ("Aceite de oliva", 20)],
  "1. Corta en ramilletes y cuece 5 min.\n2. Colócalos en una fuente con aceite y queso rallado.\n3. Gratina 15 min.", ""),
 ("bacalao-llauna", "Bacalao a la llauna", 4, 25, "", "cat", "Pescado", [("Bacalao salado (desalado, crudo)", 600), ("Ajo", 20), ("Pimentón de la Vera", 3), ("Aceite de oliva virgen extra (arbequina)", 40), ("Vino blanco", 50)],
  "1. Dora el ajo laminado y añade el pimentón y el vino.\n2. Pon el bacalao enharinado y cuece 8 min.\n3. Sirve con la salsa.", ""),
 # ---- todo el año
 ("tortilla-patatas", "Tortilla de patatas", 4, 35, "", "es", "Plato ligero", [("Patata (cruda)", 600), ("Huevo entero", 440), ("Cebolla", 150), ("Aceite de oliva", 80)],
  "1. Pocha la patata y la cebolla en aceite.\n2. Mezcla con los huevos batidos.\n3. Cuaja por ambos lados.", ""),
 ("pulpo-gallega", "Pulpo a la gallega", 4, 60, "", "es", "Pescado", [("Pulpo (cocido)", 600), ("Patata (cruda)", 500), ("Pimentón de la Vera", 4), ("Aceite de oliva", 40)],
  "1. Cuece las patatas y córtalas en rodajas.\n2. Corta el pulpo en rodajas.\n3. Aliña con aceite, pimentón y sal gruesa.", ""),
 ("fideua", "Fideuà", 4, 45, "", "cat", "Arroces", [("Fideos (crudos)", 280), ("Calamar", 200), ("Gambas / langostinos (cocidos)", 200), ("Sofrito catalán", 100), ("Aceite de oliva", 30), ("Caldo de verduras", 700), ("Allioli", 30)],
  "1. Dora los fideos en la paella con aceite.\n2. Añade el sofrito, el calamar y el caldo caliente.\n3. Cuece 10 min, pon las gambas y sirve con allioli.", ""),
 ("arroz-negro", "Arroz negro", 4, 45, "", "cat", "Arroces", [("Arroz bomba / del Delta (crudo)", 280), ("Sepia", 400), ("Sofrito catalán", 100), ("Allioli", 30), ("Caldo de verduras", 800), ("Aceite de oliva", 20)],
  "1. Sofríe la sepia con el sofrito.\n2. Añade el arroz y el caldo con tinta.\n3. Cuece 18 min y sirve con allioli.", ""),
 ("paella", "Paella de pollo y conejo", 4, 60, "", "es", "Arroces", [("Arroz bomba / del Delta (crudo)", 280), ("Pollo de corral (cocinado)", 300), ("Conejo (cocinado)", 300), ("Judías verdes", 150), ("Tomate", 200), ("Pimentón de la Vera", 3), ("Azafrán", 0.5), ("Aceite de oliva", 40), ("Caldo de pollo / carne", 800)],
  "1. Dora las carnes en la paella.\n2. Añade verdura, tomate, pimentón y el caldo con azafrán.\n3. Echa el arroz, cuece 18 min sin remover y reposa 5.", ""),
 ("zarzuela", "Zarzuela de pescado", 4, 50, "", "cat", "Pescado", [("Rape (cocinado)", 300), ("Merluza (cruda)", 300), ("Mejillones (cocidos)", 200), ("Gambas / langostinos (cocidos)", 200), ("Sofrito catalán", 150), ("Almendras", 20), ("Caldo de verduras", 300), ("Aceite de oliva", 30)],
  "1. Sofríe el sofrito y añade el caldo con las almendras picadas.\n2. Incorpora los pescados en orden de dureza.\n3. Cuece 10 min y termina con los mariscos.", ""),
 ("dorada-horno", "Dorada al horno con patatas", 3, 50, "", "es", "Pescado", [("Dorada", 600), ("Patata (cruda)", 400), ("Cebolla", 100), ("Pimiento verde", 100), ("Tomate", 150), ("Aceite de oliva", 30)],
  "1. Hornea las patatas con cebolla y pimiento 20 min a 200 °C.\n2. Coloca la dorada encima con el tomate.\n3. Hornea 20 min más.", ""),
 ("merluza-verde", "Merluza en salsa verde con almejas", 4, 30, "", "es", "Pescado", [("Merluza (cruda)", 600), ("Almejas (cocidas)", 200), ("Ajo", 15), ("Aceite de oliva", 30), ("Vino blanco", 50)],
  "1. Dora el ajo, añade el vino y las almejas hasta que abran.\n2. Añade la merluza y cuece 6 min moviendo la cazuela.", ""),
 ("conejo-ajillo", "Conejo al ajillo", 4, 45, "", "es", "Plato de carne", [("Conejo (cocinado)", 600), ("Ajo", 30), ("Vino blanco", 100), ("Aceite de oliva", 30)],
  "1. Dora el conejo troceado con los ajos con piel.\n2. Añade el vino y deja reducir.\n3. Cuece tapado 30 min.", ""),
 ("mel-mato", "Mel i mató", 4, 5, "", "cat", "Postre", [("Mató (queso fresco)", 240), ("Miel", 40), ("Nueces", 30)],
  "1. Reparte el mató en cuencos.\n2. Cubre con miel y nueces troceadas.", ""),
 ("garbanzos-cebolla", "Garbanzos con bacalao y espinacas", 4, 30, "10-5", "es", "Plato de cuchara", [("Garbanzos (cocidos)", 500), ("Bacalao salado (desalado, crudo)", 300), ("Espinacas", 300), ("Ajo", 10), ("Aceite de oliva", 30)],
  "1. Dora el ajo y añade las espinacas.\n2. Incorpora los garbanzos y el bacalao desmigado.\n3. Cuece 10 min.", ""),
]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    foods = {f["name"]: f["id"] for f in json.load(open(os.path.join(here, "..", "data", "foods.json"), encoding="utf-8"))}
    out, bad = [], []
    for uid, name, sv, mins, mo, org, kind, items, steps, note in R:
        its = []
        for n, g in items:
            if n not in foods:
                bad.append((uid, n)); continue
            its.append({"food_id": foods[n], "grams": g})
        out.append({"uid": "lib_" + uid, "name": name, "servings": sv, "minutes": mins, "months": months(mo), "origin": org, "kind": kind, "items": its, "steps": steps, "notes": note})
    if bad:
        print("INGREDIENTES QUE NO EXISTEN:", bad); sys.exit(1)
    with open(os.path.join(here, "..", "data", "recipes.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(len(out), "recetas")


if __name__ == "__main__":
    main()
