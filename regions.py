"""
regions.py — Régions officielles de Madagascar (22 régions + Diaspora)
Importé par account, post, group et bazar pour la feature "Près de chez moi".
"""

REGION_CHOICES = [
    ('', 'Toute Madagascar'),
    # ── Hauts Plateaux ──────────────────────────────────────────────────────
    ('analamanga',        'Analamanga · Antananarivo'),
    ('vakinankaratra',    'Vakinankaratra · Antsirabe'),
    ('itasy',             'Itasy · Miarinarivo'),
    ('bongolava',         'Bongolava · Tsiroanomandidy'),
    # ── Centre / Sud-Ouest ──────────────────────────────────────────────────
    ('haute_matsiatra',   'Haute Matsiatra · Fianarantsoa'),
    ('amoron_i_mania',    "Amoron'i Mania · Ambositra"),
    ('vatovavy',          'Vatovavy · Mananjary'),
    ('fitovinany',        'Fitovinany · Manakara'),
    ('ihorombe',          'Ihorombe · Ihosy'),
    ('atsimo_atsinanana', 'Atsimo-Atsinanana · Farafangana'),
    # ── Est ─────────────────────────────────────────────────────────────────
    ('atsinanana',        'Atsinanana · Toamasina'),
    ('analanjirofo',      'Analanjirofo · Fenoarivo Atsinanana'),
    ('alaotra_mangoro',   'Alaotra-Mangoro · Ambatondrazaka'),
    # ── Nord-Ouest ──────────────────────────────────────────────────────────
    ('boeny',             'Boeny · Mahajanga'),
    ('sofia',             'Sofia · Antsohihy'),
    ('betsiboka',         'Betsiboka · Maevatanana'),
    ('melaky',            'Melaky · Maintirano'),
    # ── Sud ─────────────────────────────────────────────────────────────────
    ('atsimo_andrefana',  'Atsimo-Andrefana · Toliara'),
    ('androy',            'Androy · Ambovombe'),
    ('anosy',             'Anosy · Tolagnaro'),
    ('menabe',            'Menabe · Morondava'),
    # ── Nord ────────────────────────────────────────────────────────────────
    ('diana',             'Diana · Antsiranana'),
    ('sava',              'Sava · Sambava'),
    # ── Hors Madagascar ─────────────────────────────────────────────────────
    ('diaspora',          '🌍 Diaspora malgache'),
]

# Dictionnaire slug → label (pour les templates et les vues)
REGION_LABELS = dict(REGION_CHOICES)

# Juste les codes valides (sans la valeur vide)
REGION_CODES = [code for code, _ in REGION_CHOICES if code]
