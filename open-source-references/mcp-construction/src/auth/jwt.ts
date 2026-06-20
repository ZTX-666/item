import { importPKCS8, importSPKI, SignJWT, jwtVerify, type JWTPayload, type KeyLike } from 'jose';
import { config, getJwtPrivateKey, getJwtPublicKey } from '../config.js';

export interface TokenPayload extends JWTPayload {
  sub: string;
  scope: string;
  org_id: string;
  plan: string;
  client_id: string;
}

export interface UserContext {
  userId: string;
  orgId: string;
  plan: string;
  scopes: string[];
  clientId: string;
}

let _privateKey: KeyLike | undefined;
let _publicKey: KeyLike | undefined;

async function getPrivateKey(): Promise<KeyLike> {
  if (!_privateKey) {
    _privateKey = await importPKCS8(getJwtPrivateKey(), 'RS256');
  }
  return _privateKey;
}

async function getPublicKey(): Promise<KeyLike> {
  if (!_publicKey) {
    _publicKey = await importSPKI(getJwtPublicKey(), 'RS256');
  }
  return _publicKey;
}

export async function createAccessToken(payload: {
  userId: string;
  orgId: string;
  scope: string;
  plan: string;
  clientId: string;
}): Promise<string> {
  const privateKey = await getPrivateKey();
  return new SignJWT({
    scope: payload.scope,
    org_id: payload.orgId,
    plan: payload.plan,
    client_id: payload.clientId,
  })
    .setProtectedHeader({ alg: 'RS256' })
    .setIssuer(config.JWT_ISSUER)
    .setSubject(payload.userId)
    .setAudience(config.JWT_AUDIENCE)
    .setIssuedAt()
    .setExpirationTime('1h')
    .sign(privateKey);
}

export async function verifyAccessToken(token: string): Promise<UserContext> {
  const publicKey = await getPublicKey();
  const { payload } = await jwtVerify(token, publicKey, {
    issuer: config.JWT_ISSUER,
    audience: config.JWT_AUDIENCE,
  });

  const p = payload as TokenPayload;
  return {
    userId: p.sub!,
    orgId: p.org_id,
    plan: p.plan,
    scopes: (p.scope || '').split(' ').filter(Boolean),
    clientId: p.client_id,
  };
}
