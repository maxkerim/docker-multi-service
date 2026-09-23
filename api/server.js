const express = require("express");
const fs = require("fs");
const { MongoClient } = require("mongodb");
const { createClient } = require("redis");

const app = express();
const PORT = 3000;

const MONGO_HOST = process.env.MONGO_HOST || "mongodb";
const MONGO_PORT = process.env.MONGO_PORT || "27017";
const MONGO_USER = process.env.MONGO_USER || "admin";

const MONGO_PASSWORD_FILE =
process.env.MONGO_PASSWORD_FILE || "/run/secrets/mongo_password";

const REDIS_URL =
process.env.REDIS_URL || "redis://redis:6379";

const mongoPassword = fs
.readFileSync(MONGO_PASSWORD_FILE, "utf8")
.trim();

const MONGO_URL =
"mongodb://" +
encodeURIComponent(MONGO_USER) +
":" +
encodeURIComponent(mongoPassword) +
"@" +
MONGO_HOST +
":" +
MONGO_PORT +
"/?authSource=admin";

const mongoClient = new MongoClient(MONGO_URL);

const redisClient = createClient({
url: REDIS_URL
});

redisClient.on("error", (error) => {
console.error("Redis error:", error);
});

app.use(express.json());

app.get("/api/health", async (req, res) => {
try {
await mongoClient.db("admin").command({ ping: 1 });
await redisClient.ping();

res.json({
  status: "ok",
  mongodb: "ok",
  redis: "ok"
});

} catch (error) {
res.status(503).json({
status: "error",
message: error.message
});
}
});

app.get("/api/items", async (req, res) => {
try {
const cachedItems = await redisClient.get("items");

if (cachedItems) {
  console.log("Cache hit");
  return res.json(JSON.parse(cachedItems));
}

console.log("Cache miss");

const db = mongoClient.db("dockerapp");
const collection = db.collection("items");

let items = await collection.find().toArray();

if (items.length === 0) {
  const defaultItems = [
    { id: 1, name: "Docker" },
    { id: 2, name: "Ansible" },
    { id: 3, name: "Kubernetes" }
  ];

  await collection.insertMany(defaultItems);

  items = await collection.find().toArray();
}

await redisClient.setEx(
  "items",
  60,
  JSON.stringify(items)
);

res.json(items);

} catch (error) {
res.status(500).json({
error: error.message
});
}
});

async function startServer() {
try {
await mongoClient.connect();
console.log("Connected to MongoDB");

await redisClient.connect();
console.log("Connected to Redis");

app.listen(PORT, "0.0.0.0", () => {
  console.log("API server running on port " + PORT);
});

} catch (error) {
console.error("Failed to start API:", error);
process.exit(1);
}
}

startServer();
