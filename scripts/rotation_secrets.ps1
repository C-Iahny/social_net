<#
    rotation_secrets.ps1
    ────────────────────
    Fait tourner les secrets de production Vazimba exposés dans l'historique
    public du dépôt GitHub, puis applique le nouveau mot de passe
    administrateur dans le conteneur en cours d'exécution.

    À lancer depuis la racine du projet, connecté à Railway (`railway whoami`) :

        powershell -ExecutionPolicy Bypass -File scripts\rotation_secrets.ps1

    Les valeurs sont générées en mémoire et transmises à Railway via stdin :
    elles n'apparaissent ni en ligne de commande, ni dans l'historique du
    terminal, ni dans un fichier. Le nouveau mot de passe administrateur est
    affiché UNE SEULE FOIS à la fin — notez-le à ce moment-là.

    ⚠ Conséquences immédiates, assumées et voulues :
      · SECRET_KEY  → toutes les sessions sont invalidées, chaque utilisateur
                      devra se reconnecter, et les liens de réinitialisation de
                      mot de passe déjà envoyés cessent de fonctionner.
      · VAPID       → les abonnements aux notifications push deviennent
                      invalides ; ils sont supprimés automatiquement au premier
                      échec d'envoi, et les utilisateurs devront réautoriser
                      les notifications dans leur navigateur.

    Ce script ne touche PAS à la clé Africa's Talking : elle doit être révoquée
    puis regénérée depuis le tableau de bord du fournisseur, avant d'être
    réinjectée avec :
        railway variable set AT_API_KEY=<nouvelle_cle>
#>

$ErrorActionPreference = 'Stop'

function Etape($n, $texte) { Write-Host "`n[$n] $texte" -ForegroundColor Cyan }

# ── Contrôles préalables ─────────────────────────────────────────────────────
Etape 0 "Verification de l'environnement"
if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    throw "Railway CLI introuvable. Installez-le : npm i -g @railway/cli"
}
railway whoami | Out-Null
$statut = railway status 2>&1 | Out-String
if ($statut -notmatch 'Service') { throw "Aucun service Railway lie. Lancez d'abord : railway link" }
Write-Host $statut.Trim()

# ── Génération ───────────────────────────────────────────────────────────────
Etape 1 "Generation des nouveaux secrets"

$py = @'
import base64, secrets, string, json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.utils import get_random_secret_key

cle = ec.generate_private_key(ec.SECP256R1())
pub = base64.urlsafe_b64encode(
    cle.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint)
).decode().rstrip('=')
priv = base64.b64encode(
    cle.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption())
).decode()

alpha = string.ascii_letters + string.digits + '!@#$%^&*-_=+'
print(json.dumps({
    'SECRET_KEY':        get_random_secret_key(),
    'VAPID_PUBLIC_KEY':  pub,
    'VAPID_PRIVATE_KEY': priv,
    'ADMIN_PASSWORD':    ''.join(secrets.choice(alpha) for _ in range(32)),
}))
'@

$env:DJANGO_SETTINGS_MODULE = 'ZOOT.settings'
$secrets = ($py | python -) | ConvertFrom-Json

foreach ($k in @('SECRET_KEY','VAPID_PUBLIC_KEY','VAPID_PRIVATE_KEY','ADMIN_PASSWORD')) {
    Write-Host ("    {0,-20} genere ({1} caracteres)" -f $k, $secrets.$k.Length)
}

# ── Installation sur Railway ─────────────────────────────────────────────────
# --skip-deploys pour ne declencher qu'un seul redeploiement, a la fin.
Etape 2 "Installation sur Railway"
foreach ($k in @('SECRET_KEY','VAPID_PUBLIC_KEY','VAPID_PRIVATE_KEY','ADMIN_PASSWORD')) {
    $secrets.$k | railway variable set --stdin $k --skip-deploys | Out-Null
    Write-Host "    $k : installe"
}

# ── Suppression des variables mortes ─────────────────────────────────────────
Etape 3 "Suppression des variables inutilisees"
foreach ($v in @('EMAIL_HOST_USER','EMAIL_HOST_PASSWORD',
                 'DJANGO_SUPERUSER_EMAIL','DJANGO_SUPERUSER_PASSWORD',
                 'DJANGO_SUPERUSER_USERNAME')) {
    try { railway variable delete $v 2>&1 | Out-Null; Write-Host "    $v : supprimee" }
    catch { Write-Host "    $v : deja absente" -ForegroundColor DarkGray }
}

# ── Redéploiement ────────────────────────────────────────────────────────────
Etape 4 "Redeploiement avec les nouveaux secrets"
railway redeploy --yes 2>&1 | Out-Null
Write-Host "    Redeploiement demande. Attente de la mise en service..."

for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 20
    $ligne = (railway deployment list 2>&1 | Out-String) -split "`n" |
             Where-Object { $_ -match '\|' } | Select-Object -First 1
    if ($ligne -match '\|\s*([A-Z_]+)\s*\|') {
        $st = $matches[1].Trim()
        if ($st -notin @('BUILDING','DEPLOYING','INITIALIZING','QUEUED','WAITING')) {
            Write-Host "    Statut final : $st"
            if ($st -ne 'SUCCESS') { throw "Deploiement en echec — secrets installes mais non actifs." }
            break
        }
    }
}

# ── Application du mot de passe administrateur ───────────────────────────────
# ensure_admin ne reinitialise plus le mot de passe automatiquement (il
# promouvait silencieusement tout compte portant ADMIN_EMAIL) : il faut le
# demander explicitement, dans le conteneur qui a acces a la base interne.
Etape 5 "Application du mot de passe administrateur"
railway ssh python manage.py ensure_admin --reset-password

# ── Vérification ─────────────────────────────────────────────────────────────
Etape 6 "Verification du site"
$r = Invoke-WebRequest "https://www.vazimba.io/" -UseBasicParsing -TimeoutSec 30
Write-Host "    https://www.vazimba.io/ : $($r.StatusCode)"

Write-Host "`n────────────────────────────────────────────────────────────" -ForegroundColor Green
Write-Host " ROTATION TERMINEE" -ForegroundColor Green
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor Green
Write-Host " Nouveau mot de passe administrateur (notez-le maintenant) :"
Write-Host ""
Write-Host "     $($secrets.ADMIN_PASSWORD)" -ForegroundColor Yellow
Write-Host ""
Write-Host " Il reste a faire, hors de portee de ce script :"
Write-Host "   - Revoquer et regenerer la cle Africa's Talking, puis :"
Write-Host "       railway variable set AT_API_KEY=<nouvelle_cle>"
Write-Host "   - Decider du sort du depot public (le passer en prive, ou"
Write-Host "     accepter que l'historique reste lisible)."
Write-Host "────────────────────────────────────────────────────────────" -ForegroundColor Green
