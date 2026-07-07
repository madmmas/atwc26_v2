// Map extensionless paths to Next.js static export files (e.g. /standings -> /standings/index.html).
// Attached only to the S3 default cache behavior — /api/* uses a separate behavior.
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith("/")) {
    request.uri += "index.html";
  } else if (!uri.includes(".")) {
    request.uri += "/index.html";
  }

  return request;
}
