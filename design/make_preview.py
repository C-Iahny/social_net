"""Reconstruit un HTML autonome depuis un .dc.html pour capture d'écran.

Retire l'enveloppe Design Component (<x-dc>, <helmet>, le script de logique),
remonte le contenu du <helmet> dans le <head> et remplace les valeurs de tweak
par leur défaut — le reste du balisage est identique à celui de l'artboard.
"""
import io, re, sys

src_path, out_path = sys.argv[1], sys.argv[2]
s = io.open(src_path, encoding='utf-8').read()

helmet = re.search(r'<helmet>(.*?)</helmet>', s, re.S)
head_extra = helmet.group(1) if helmet else ''

body = re.search(r'<x-dc>(.*?)</x-dc>', s, re.S).group(1)
body = re.sub(r'<helmet>.*?</helmet>', '', body, flags=re.S)
body = body.replace('{{accent}}', '#8B4513')

io.open(out_path, 'w', encoding='utf-8', newline='\n').write(
    '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
    + head_extra
    + '<style>body{margin:0}</style></head><body>'
    + body
    + '</body></html>'
)
print(f'{out_path} ecrit ({len(body)} caracteres de balisage)')
