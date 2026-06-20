import { generateKeyPair } from 'node:crypto';
import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const keysDir = join(__dirname, '..', 'keys');

if (!existsSync(keysDir)) {
  mkdirSync(keysDir, { recursive: true });
}

generateKeyPair(
  'rsa',
  {
    modulusLength: 2048,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
  },
  (err, publicKey, privateKey) => {
    if (err) {
      console.error('Failed to generate key pair:', err);
      process.exit(1);
    }

    writeFileSync(join(keysDir, 'public.pem'), publicKey);
    writeFileSync(join(keysDir, 'private.pem'), privateKey);

    console.log('RSA key pair generated successfully:');
    console.log(`  Private key: ${join(keysDir, 'private.pem')}`);
    console.log(`  Public key:  ${join(keysDir, 'public.pem')}`);
  },
);
