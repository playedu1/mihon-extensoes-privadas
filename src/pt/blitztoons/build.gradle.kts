import io.github.keiyoushi.gradle.api.ContentWarning

plugins {
    alias(kei.plugins.extension)
}

keiyoushi {
    name = "BlitzToons"
    versionCode = 1
    contentWarning = ContentWarning.MIXED
    libVersion = "1.6"

    source {
        name = "BlitzToons"
        lang = "pt-BR"
        baseUrl = "https://blitztoons.com"
    }

    deeplink {
        path("/obra/..*")
    }
}
