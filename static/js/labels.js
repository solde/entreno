export const MUSCLE = { abdominals: "Abdominales", abductors: "Abductores", adductors: "Aductores", biceps: "Bíceps", calves: "Gemelos", chest: "Pecho", forearms: "Antebrazos", glutes: "Glúteos", hamstrings: "Isquiotibiales", lats: "Dorsales", "lower back": "Lumbares", "middle back": "Espalda media", neck: "Cuello", quadriceps: "Cuádriceps", shoulders: "Hombros", traps: "Trapecios", triceps: "Tríceps" };
export const EQUIP = { barbell: "Barra", dumbbell: "Mancuernas", "body only": "Peso corporal", cable: "Polea", machine: "Máquina", kettlebells: "Pesa rusa", bands: "Bandas", "medicine ball": "Balón medicinal", "exercise ball": "Fitball", "foam roll": "Rodillo", "e-z curl bar": "Barra Z", other: "Otro", none: "Sin material" };
export const CAT = { strength: "Fuerza", cardio: "Cardio", stretching: "Estiramientos", plyometrics: "Pliométricos", powerlifting: "Powerlifting", "olympic weightlifting": "Halterofilia", strongman: "Strongman" };
export const LEVEL = { beginner: "Principiante", intermediate: "Intermedio", expert: "Avanzado" };
export const TRACK = { reps: "Series y repeticiones", time: "Por tiempo", cardio: "Cardio (tiempo y distancia)" };
export const WEEKDAY = ["", "L", "M", "X", "J", "V", "S", "D"];
export const WEEKDAY_LONG = ["", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
export const lab = (map, k) => map[k] || k;
export const exName = (e) => e.name_es || e.name;

export const SLOT = { breakfast: "Desayuno", snack_am: "Media mañana", lunch: "Comida", snack_pm: "Merienda", dinner: "Cena", other: "Otros" };
export const SLOTS = Object.keys(SLOT);
export const ACTIVITY = { sedentary: "Sedentaria (poco o nada de ejercicio)", light: "Ligera (1-3 días/semana)", moderate: "Moderada (3-5 días/semana)", active: "Alta (6-7 días/semana)", very_active: "Muy alta (entrenos dobles o trabajo físico)" };
