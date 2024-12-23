# A note on encryption #

Limesurvey offers data encryption. This is needed to be GDPR-compliant. Therefore several encryption keys are needed. Limesurvey will create them automatically when needed, but this is not an option, because reinstalling (or running several instances) will create new keys, so existing data cannot be set any more. Consequently we need to set encryption keys during installation.

Only there is no documentation how to create encryption keys. The following lines are extracted from the limesurvey source code, it's how limesurvey creates the keys. It requires a correctly set up PHP environment. For simplicity the limesurvey container itself can be used to execute these commands:

```bash
php_code=$(cat <<'EOF'
require_once './vendor/paragonie/sodium_compat/src/Core/Util.php';
require_once './vendor/paragonie/sodium_compat/src/Compat.php';
$sEncryptionNonce = sodium_bin2hex(random_bytes(ParagonIE_Sodium_Compat::CRYPTO_SECRETBOX_NONCEBYTES));
$sEncryptionSecretBoxKey = sodium_bin2hex(ParagonIE_Sodium_Compat::crypto_secretbox_keygen());
$sEncryptionKeypair = ParagonIE_Sodium_Compat::crypto_sign_keypair();
$sEncryptionPublicKey = ParagonIE_Sodium_Compat::bin2hex(ParagonIE_Sodium_Compat::crypto_sign_publickey($sEncryptionKeypair));
$sEncryptionSecretKey = ParagonIE_Sodium_Compat::bin2hex(ParagonIE_Sodium_Compat::crypto_sign_secretkey($sEncryptionKeypair));
$sEncryptionKeypair = ParagonIE_Sodium_Compat::bin2hex($sEncryptionKeypair);

echo "encryptionnonce: $sEncryptionNonce\n";
echo "encryptionsecretboxKey: $sEncryptionSecretBoxKey\n";
echo "encryptionkeypair: $sEncryptionKeypair\n";
echo "encryptionpublickey: $sEncryptionPublicKey\n";
echo "encryptionsecretkey: $sEncryptionSecretKey\n";
EOF
)
php -r "$php_code"
```