package mg.vazimba.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        /* Enregistrer le plugin audio AVANT super.onCreate() */
        registerPlugin(VzbAudioPlugin.class);
        super.onCreate(savedInstanceState);
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
