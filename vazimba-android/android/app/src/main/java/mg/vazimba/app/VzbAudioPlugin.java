package mg.vazimba.app;

import android.content.Context;
import android.media.AudioManager;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * VzbAudioPlugin — contrôle du routage audio pendant un appel WebRTC.
 *
 * Par défaut Android WebView route l'audio WebRTC vers le haut-parleur
 * (STREAM_MUSIC). Ce plugin bascule en MODE_IN_COMMUNICATION (écouteur)
 * au début d'un appel et remet le mode normal à la fin.
 *
 * Appelé depuis room.html via :
 *   window.Capacitor.Plugins.VzbAudio.setMode({ mode: 'call' })
 *   window.Capacitor.Plugins.VzbAudio.setSpeaker({ on: true })
 *   window.Capacitor.Plugins.VzbAudio.setMode({ mode: 'normal' })
 */
@CapacitorPlugin(name = "VzbAudio")
public class VzbAudioPlugin extends Plugin {

    private AudioManager getAm() {
        return (AudioManager) getContext().getSystemService(Context.AUDIO_SERVICE);
    }

    /**
     * setMode({ mode: 'call' | 'speaker' | 'normal' })
     *   'call'    → MODE_IN_COMMUNICATION + haut-parleur OFF  (écouteur)
     *   'speaker' → MODE_IN_COMMUNICATION + haut-parleur ON
     *   'normal'  → MODE_NORMAL           + haut-parleur OFF
     */
    @PluginMethod
    public void setMode(PluginCall call) {
        String mode = call.getString("mode", "normal");
        AudioManager am = getAm();
        if (am == null) { call.resolve(); return; }

        if ("call".equals(mode)) {
            am.setMode(AudioManager.MODE_IN_COMMUNICATION);
            am.setSpeakerphoneOn(false);
        } else if ("speaker".equals(mode)) {
            am.setMode(AudioManager.MODE_IN_COMMUNICATION);
            am.setSpeakerphoneOn(true);
        } else {
            // 'normal' ou toute autre valeur → restaurer état par défaut
            am.setSpeakerphoneOn(false);
            am.setMode(AudioManager.MODE_NORMAL);
        }
        call.resolve();
    }

    /**
     * setSpeaker({ on: true | false })
     * Bascule haut-parleur sans changer le mode audio.
     * À appeler uniquement pendant un appel actif (mode déjà IN_COMMUNICATION).
     */
    @PluginMethod
    public void setSpeaker(PluginCall call) {
        Boolean on = call.getBoolean("on", false);
        AudioManager am = getAm();
        if (am != null) {
            am.setSpeakerphoneOn(on != null && on);
        }
        call.resolve();
    }
}
