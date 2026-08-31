package cn.cet.learningdesk;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.os.Bundle;

import java.io.File;

/**
 * Release-upgrade probe which is compiled only into the androidTest APK.
 *
 * This class never ships in the production application. It writes and reads a
 * non-secret marker through the real Android Keystore-backed SecureStore and
 * checks a real SQLite note after a same-signature package replacement.
 */
public final class UpgradeProbeInstrumentation extends Instrumentation {
    private static final String KEYSTORE_SENTINEL =
            "upgrade-keystore-sentinel-20260831";
    private static final String DATABASE_SENTINEL =
            "upgrade-retention-20260831-0429";

    private Bundle arguments;

    @Override
    public void onCreate(Bundle args) {
        super.onCreate(args);
        arguments = args == null ? new Bundle() : args;
        start();
    }

    @Override
    public void onStart() {
        Bundle result = new Bundle();
        try {
            Context target = getTargetContext();
            SecureStore.init(target);
            String mode = arguments.getString("mode", "verify");
            if ("write".equals(mode)) {
                SecureStore.setApiKey(KEYSTORE_SENTINEL);
                result.putString("keystore", "written");
            } else {
                String actual = SecureStore.getApiKey();
                if (!KEYSTORE_SENTINEL.equals(actual)) {
                    throw new IllegalStateException("Keystore sentinel is missing after upgrade");
                }
                result.putString("keystore", "retained");
            }

            File databaseFile = new File(target.getFilesDir(), "data/vocab.db");
            if (!databaseFile.isFile()) {
                throw new IllegalStateException("SQLite database is missing");
            }
            try (SQLiteDatabase database = SQLiteDatabase.openDatabase(
                    databaseFile.getAbsolutePath(), null, SQLiteDatabase.OPEN_READONLY);
                 Cursor cursor = database.rawQuery(
                         "SELECT COUNT(*) FROM notes WHERE content=?",
                         new String[]{DATABASE_SENTINEL})) {
                if (!cursor.moveToFirst() || cursor.getInt(0) != 1) {
                    throw new IllegalStateException("SQLite upgrade sentinel is missing or duplicated");
                }
            }
            result.putString("sqlite", "retained");
            result.putString("probe", "ok");
            finish(Activity.RESULT_OK, result);
        } catch (Throwable error) {
            result.putString("probe", "failed");
            result.putString("error", error.getClass().getSimpleName() + ": " + error.getMessage());
            finish(Activity.RESULT_CANCELED, result);
        }
    }
}
