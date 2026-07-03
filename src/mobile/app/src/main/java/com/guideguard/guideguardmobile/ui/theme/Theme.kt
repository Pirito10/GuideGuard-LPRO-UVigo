package com.guideguard.guideguardmobile.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = GG_PrimaryBlue,
    secondary = GG_SecondaryCyan,
    background = GG_Background,
    error = GG_ErrorRed,
    onPrimary = Color.White,
    onBackground = GG_PrimaryBlue
)

@Composable
fun GuideGuardMobileTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColorScheme,
        typography = AppTypography,
        content = content
    )
}