package cn.cet.learningdesk;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public final class SecureStore {
    private static final String KEY_ALIAS = "CETLearningDesk.DeepSeek";
    private static final String PREFS = "cet_secure_preferences";
    private static final String API_KEY = "deepseek_api_key";
    private static Context context;

    private SecureStore() {}

    public static synchronized void init(Context appContext) {
        context = appContext.getApplicationContext();
    }

    private static SharedPreferences preferences() {
        if (context == null) {
            throw new IllegalStateException("SecureStore 尚未初始化");
        }
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) store.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build());
        return generator.generateKey();
    }

    public static synchronized String encrypt(String value) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        byte[] iv = cipher.getIV();
        ByteBuffer payload = ByteBuffer.allocate(4 + iv.length + encrypted.length);
        payload.putInt(iv.length);
        payload.put(iv);
        payload.put(encrypted);
        return Base64.encodeToString(payload.array(), Base64.NO_WRAP);
    }

    public static synchronized String decrypt(String encoded) throws Exception {
        byte[] raw = Base64.decode(encoded, Base64.NO_WRAP);
        ByteBuffer payload = ByteBuffer.wrap(raw);
        int ivLength = payload.getInt();
        if (ivLength < 12 || ivLength > 32 || payload.remaining() <= ivLength) {
            throw new IllegalArgumentException("无效的加密数据");
        }
        byte[] iv = new byte[ivLength];
        payload.get(iv);
        byte[] encrypted = new byte[payload.remaining()];
        payload.get(encrypted);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
        return new String(cipher.doFinal(encrypted), StandardCharsets.UTF_8);
    }

    public static synchronized void setApiKey(String value) throws Exception {
        preferences().edit().putString(API_KEY, encrypt(value)).apply();
    }

    public static synchronized String getApiKey() {
        String encoded = preferences().getString(API_KEY, "");
        if (encoded == null || encoded.isEmpty()) {
            return "";
        }
        try {
            return decrypt(encoded);
        } catch (Exception ignored) {
            return "";
        }
    }

    public static synchronized void deleteApiKey() {
        preferences().edit().remove(API_KEY).apply();
    }
}
