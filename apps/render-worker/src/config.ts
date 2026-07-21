function required(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value === undefined) {
    throw new Error(`Missing required env var ${name}`);
  }
  return value;
}

export const config = {
  port: Number(process.env.PORT ?? 3001),
  r2AccountId: process.env.R2_ACCOUNT_ID ?? "",
  r2AccessKeyId: required("R2_ACCESS_KEY_ID", ""),
  r2SecretAccessKey: required("R2_SECRET_ACCESS_KEY", ""),
  r2BucketName: process.env.R2_BUCKET_NAME ?? "viralcut-assets",
  // Overrides the computed R2 endpoint; used in dev to point at MinIO instead,
  // same convention as the Python services' R2_ENDPOINT_URL.
  r2EndpointUrl: process.env.R2_ENDPOINT_URL || undefined,
};
