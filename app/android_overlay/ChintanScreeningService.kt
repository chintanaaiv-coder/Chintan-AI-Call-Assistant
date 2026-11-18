package com.chintanai.chintan_assistant

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import android.telecom.Call
import android.telecom.CallScreeningService

/**
 * Android asks this service about every incoming call before it rings.
 * Calls Chintan should handle are declined here; the mobile network's
 * "forward when busy" setting (**67*) then sends them to the Chintan server.
 */
class ChintanScreeningService : CallScreeningService() {

    override fun onScreenCall(details: Call.Details) {
        val incoming = details.callDirection == Call.Details.DIRECTION_INCOMING
        val number = details.handle?.schemeSpecificPart
        val screen = incoming && shouldScreen(number)

        val response = CallResponse.Builder()
        if (screen) {
            response.setDisallowCall(true)
                .setRejectCall(true)       // rejected = "busy", which triggers the network forward
                .setSkipCallLog(false)
                .setSkipNotification(true)
        }
        respondToCall(details, response.build())
        if (screen) notifyScreening(number)
    }

    private fun shouldScreen(number: String?): Boolean {
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val mode = prefs.getString("mode", "all") ?: "all"
        if (mode == "off") return false
        if (prefs.getLong("snoozed_until_ms", 0L) > System.currentTimeMillis()) return false
        if (mode == "unknown" && number != null && isContact(number)) return false
        return true
    }

    private fun isContact(number: String): Boolean {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) return false
        val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number))
        return try {
            contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup._ID), null, null, null)?.use { it.count > 0 } ?: false
        } catch (e: Exception) {
            false
        }
    }

    private fun notifyScreening(number: String?) {
        val nm = getSystemService(NotificationManager::class.java) ?: return
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Calls Chintan is answering", NotificationManager.IMPORTANCE_HIGH)
        )
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val n = Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.sym_call_incoming)
            .setContentTitle("Chintan is answering a call")
            .setContentText("From ${number ?: "a private number"}. Tap to listen in, message or join.")
            .setContentIntent(open)
            .setAutoCancel(true)
            .build()
        try {
            nm.notify((System.currentTimeMillis() % 100000).toInt(), n)
        } catch (e: SecurityException) {
            // Notifications not allowed: the call is still screened.
        }
    }

    companion object {
        const val PREFS = "chintan_screening"
        private const val CHANNEL = "chintan_calls"
    }
}
