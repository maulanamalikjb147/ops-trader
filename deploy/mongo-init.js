// MongoDB Init Script — runs on first startup
// Creates the signal_bot database with the app user

db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || 'signal_bot');

db.createUser({
  user: 'signal_bot_user',
  pwd: process.env.SIGNAL_BOT_DB_PASSWORD || 'signalbotpass123',
  roles: [
    { role: 'readWrite', db: process.env.MONGO_INITDB_DATABASE || 'signal_bot' }
  ]
});

// Create collections with validators
db.createCollection('users');
db.createCollection('signals');
db.createCollection('positions');
db.createCollection('exchange_configs');
db.createCollection('bot_config');
db.createCollection('performance_summary');

// Create indexes
db.users.createIndex({ username: 1 }, { unique: true });
db.signals.createIndex({ status: 1 });
db.signals.createIndex({ pair: 1 });
db.signals.createIndex({ created_at: -1 });
db.positions.createIndex({ signal_id: 1 });
db.performance_summary.createIndex({ period: 1, exchange: 1, trading_mode: 1 }, { unique: true });

print('Signal Bot database initialized successfully');
