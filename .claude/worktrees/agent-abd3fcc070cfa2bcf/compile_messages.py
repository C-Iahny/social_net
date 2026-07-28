"""
Compile les fichiers .po en .mo sans dépendance externe (msgfmt ou Twisted).
Utilisé au démarrage sur Railway car manage.py compilemessages échoue
à cause de la dépendance OpenSSL/Twisted.
"""
import re
import struct
import os


def parse_po(path):
    """Parse un fichier .po, gère les msgstr multilignes."""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    entries = {}
    blocks = re.split(r'\n\n+', text.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        in_msgid = False
        in_msgstr = False
        cur_id = []
        cur_str = []

        for line in lines:
            line = line.rstrip()
            if line.startswith('#'):
                continue
            elif line.startswith('msgid '):
                in_msgid = True
                in_msgstr = False
                cur_id = [line[7:-1]]
            elif line.startswith('msgstr '):
                in_msgid = False
                in_msgstr = True
                cur_str = [line[8:-1]]
            elif line.startswith('"') and line.endswith('"'):
                val = line[1:-1]
                if in_msgid:
                    cur_id.append(val)
                elif in_msgstr:
                    cur_str.append(val)

        # Si aucun msgid trouvé dans ce bloc (bloc de commentaires pure),
        # on ignore — sinon l'entrée header (msgid '') serait écrasée à ''
        if not cur_id:
            continue

        msgid_raw = ''.join(cur_id).replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
        msgstr_raw = ''.join(cur_str).replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')

        # Inclure l'entrée header (msgid vide) ET les traductions non vides
        if msgstr_raw or msgid_raw == '':
            entries[msgid_raw] = msgstr_raw

    return entries


def compile_mo(entries, mo_path):
    """Génère un fichier .mo valide (little-endian, UTF-8)."""
    keys = sorted(entries.keys())
    N = len(keys)

    key_bytes = [k.encode('utf-8') for k in keys]
    val_bytes = [entries[k].encode('utf-8') for k in keys]

    header_size    = 7 * 4   # 28 bytes
    key_table_off  = header_size
    val_table_off  = key_table_off + N * 8
    key_data_off   = val_table_off + N * 8
    val_data_off   = key_data_off + sum(len(b) + 1 for b in key_bytes)

    key_positions = []
    val_positions = []
    koff = key_data_off
    voff = val_data_off

    for kb in key_bytes:
        key_positions.append((len(kb), koff))
        koff += len(kb) + 1

    for vb in val_bytes:
        val_positions.append((len(vb), voff))
        voff += len(vb) + 1

    header = struct.pack('<IIIIIII',
        0x950412de,  # magic little-endian
        0,           # revision
        N,
        key_table_off,
        val_table_off,
        0, 0,        # hash (unused)
    )

    key_table = b''.join(struct.pack('<II', l, o) for l, o in key_positions)
    val_table = b''.join(struct.pack('<II', l, o) for l, o in val_positions)
    key_data  = b''.join(kb + b'\x00' for kb in key_bytes)
    val_data  = b''.join(vb + b'\x00' for vb in val_bytes)

    os.makedirs(os.path.dirname(mo_path), exist_ok=True)
    with open(mo_path, 'wb') as f:
        f.write(header + key_table + val_table + key_data + val_data)

    return N


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    ok = True
    for lang in ['fr', 'en', 'mg']:
        po = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.po')
        mo = os.path.join(base, 'locale', lang, 'LC_MESSAGES', 'django.mo')
        if not os.path.exists(po):
            print(f'  [{lang}] .po introuvable : {po}')
            ok = False
            continue
        try:
            entries = parse_po(po)
            n = compile_mo(entries, mo)
            print(f'  [{lang}] {n} entrées → {mo}')
        except Exception as e:
            print(f'  [{lang}] ERREUR : {e}')
            ok = False

    if not ok:
        raise SystemExit(1)
    print('Compilation .mo terminée.')
