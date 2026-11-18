package com.chintanai.chintan_assistant

import android.Manifest
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private var pendingRoleResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "chintan/native").setMethodCallHandler { call, result ->
            when (call.method) {
                "hasRole" -> result.success(hasRole())
                "requestRole" -> requestRole(result)
                "configure" -> {
                    val prefs = getSharedPreferences(ChintanScreeningService.PREFS, Context.MODE_PRIVATE)
                    prefs.edit()
                        .putString("mode", call.argument<String>("mode") ?: "all")
                        .putLong("snoozed_until_ms", (call.argument<Number>("snoozedUntilMs") ?: 0).toLong())
                        .apply()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun hasRole(): Boolean {
        val rm = getSystemService(RoleManager::class.java) ?: return false
        return rm.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
    }

    private fun requestRole(result: MethodChannel.Result) {
        // Contacts (for "only unknown numbers") and notifications ("Chintan is answering...").
        val perms = mutableListOf(Manifest.permission.READ_CONTACTS)
        if (Build.VERSION.SDK_INT >= 33) perms.add(Manifest.permission.POST_NOTIFICATIONS)
        val missing = perms.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 41)

        if (hasRole()) {
            result.success(true)
            return
        }
        val rm = getSystemService(RoleManager::class.java)
        if (rm == null || !rm.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            result.success(false)
            return
        }
        pendingRoleResult = result
        @Suppress("DEPRECATION")
        startActivityForResult(rm.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), ROLE_REQUEST)
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == ROLE_REQUEST) {
            pendingRoleResult?.success(hasRole())
            pendingRoleResult = null
        }
    }

    companion object {
        private const val ROLE_REQUEST = 7001
    }
}
