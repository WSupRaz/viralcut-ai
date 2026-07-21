import fs from "node:fs";
import { Readable } from "node:stream";
import { GetObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { config } from "./config";

let client: S3Client | undefined;

function getR2Client(): S3Client {
  if (!client) {
    client = new S3Client({
      endpoint: config.r2EndpointUrl ?? `https://${config.r2AccountId}.r2.cloudflarestorage.com`,
      region: "auto",
      credentials: {
        accessKeyId: config.r2AccessKeyId,
        secretAccessKey: config.r2SecretAccessKey,
      },
      forcePathStyle: true,
    });
  }
  return client;
}

export async function downloadToPath(key: string, localPath: string): Promise<void> {
  const response = await getR2Client().send(
    new GetObjectCommand({ Bucket: config.r2BucketName, Key: key })
  );
  const body = response.Body as Readable;
  await new Promise<void>((resolve, reject) => {
    const writeStream = fs.createWriteStream(localPath);
    body.pipe(writeStream);
    body.on("error", reject);
    writeStream.on("error", reject);
    writeStream.on("finish", resolve);
  });
}

export async function uploadFromPath(
  localPath: string,
  key: string,
  contentType = "video/mp4"
): Promise<void> {
  const body = fs.readFileSync(localPath);
  await getR2Client().send(
    new PutObjectCommand({
      Bucket: config.r2BucketName,
      Key: key,
      Body: body,
      ContentType: contentType,
    })
  );
}
