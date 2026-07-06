# ══════════════════════════════════════════════════════════════════════════════
#  ProGuard / R8 rules — Vazimba (Capacitor WebView app)
# ══════════════════════════════════════════════════════════════════════════════

# ── Capacitor Bridge ─────────────────────────────────────────────────────────
-keep class com.getcapacitor.** { *; }
-keepclassmembers class com.getcapacitor.** { *; }
-keep @com.getcapacitor.annotation.CapacitorPlugin class * { *; }
-keepclassmembers class * extends com.getcapacitor.Plugin { *; }
-keep class com.getcapacitor.plugin.** { *; }

# ── MainActivity ─────────────────────────────────────────────────────────────
-keep class mg.vazimba.app.** { *; }

# ── Interface JavaScript ↔ WebView ───────────────────────────────────────────
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# ── Cordova / Capacitor plugins ──────────────────────────────────────────────
-keep class org.apache.cordova.** { *; }
-keepclassmembers class org.apache.cordova.** { *; }

# ── Annotations & signatures ─────────────────────────────────────────────────
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes EnclosingMethod
-keepattributes SourceFile,LineNumberTable

# ── Kotlin ───────────────────────────────────────────────────────────────────
-dontwarn kotlin.**
-keep class kotlin.** { *; }
-keep class kotlin.Metadata { *; }

# ── AndroidX ─────────────────────────────────────────────────────────────────
-keep class androidx.** { *; }
-keep interface androidx.** { *; }
-dontwarn androidx.**

# ── Warnings inutiles ────────────────────────────────────────────────────────
-dontwarn com.google.android.gms.**
-dontwarn com.google.firebase.**
