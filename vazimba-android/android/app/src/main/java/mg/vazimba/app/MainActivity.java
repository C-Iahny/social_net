package mg.vazimba.app;

import android.os.Bundle;
import android.webkit.WebSettings;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        /* Enregistrer le plugin audio AVANT super.onCreate() */
        registerPlugin(VzbAudioPlugin.class);
        super.onCreate(savedInstanceState);

        /* Lecture des fichiers choisis (galerie / caméra) par la page :
           sans ces deux réglages, FileReader et createImageBitmap échouent
           dans la WebView et l'aperçu d'une story restait noir. La page
           chargée est https://www.vazimba.io, pas un fichier local. */
        if (this.bridge != null && this.bridge.getWebView() != null) {
            WebSettings s = this.bridge.getWebView().getSettings();
            s.setAllowFileAccess(true);
            s.setAllowContentAccess(true);
        }
    }

    /**
     * Intercepte le bouton Retour Android.
     * - Si le WebView a un historique → revenir en arrière (navigation normale)
     * - Sinon → comportement par défaut = fermer l'activité (quitter l'app)
     */
    @Override
    public void onBackPressed() {
        if (this.bridge != null && this.bridge.getWebView().canGoBack()) {
            this.bridge.getWebView().goBack();
        } else {
            super.onBackPressed();
        }
    }
}
