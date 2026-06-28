/** @type {import('next').NextConfig} */

// Docker Compose uses standalone (default). S3 static deploy sets NEXT_OUTPUT_MODE=export.
const isStaticExport = process.env.NEXT_OUTPUT_MODE === "export";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  ...(isStaticExport
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {
        output: "standalone",
      }),
};

module.exports = nextConfig;
