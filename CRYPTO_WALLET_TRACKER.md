# Crypto Wallet Tracker - Documentation

## Overview
A full-stack web application that analyzes Ethereum wallets and calculates transaction costs, amounts spent, and received amounts using the Alchemy API.

## Features

### ✅ Implemented Features
1. **Wallet Analysis**
   - Enter any Ethereum wallet address (0x...)
   - Fetches complete transaction history using Alchemy API
   - Analyzes up to 1000 outgoing and 1000 incoming transactions

2. **Calculations**
   - **Total ETH Sent**: Sum of all outgoing ETH transactions
   - **Total ETH Received**: Sum of all incoming ETH transactions
   - **Total Gas Fees**: Sum of gas costs (gasUsed × effectiveGasPrice) for up to 100 transactions
   - **Net Balance**: Received - Sent - Gas Fees

3. **ERC-20 Token Support**
   - Tracks ERC-20 token transfers (sent and received)
   - Supports major tokens like USDT, USDC, DAI, LINK, UNI, etc.
   - Displays token symbols and amounts

4. **Transaction History**
   - Shows up to 20 most recent transactions
   - Transaction type (Sent/Received)
   - Asset type (ETH or token symbol)
   - Transaction hash (clickable link to Etherscan)
   - Amount transferred
   - From/To addresses

5. **Modern UI**
   - Beautiful gradient purple background
   - Color-coded summary cards (green for received, red for sent, orange for fees, blue for net)
   - Responsive design using Tailwind CSS
   - shadcn/ui components
   - Loading states and error handling

6. **Data Persistence**
   - Stores wallet analyses in MongoDB
   - API endpoint to retrieve analysis history

## Technical Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: MongoDB (Motor async driver)
- **Blockchain API**: Alchemy API
- **Packages**: 
  - `web3` - Ethereum utilities
  - `requests` - HTTP requests to Alchemy
  - `motor` - Async MongoDB driver

### Frontend
- **Framework**: React 19
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (Radix UI)
- **Icons**: Lucide React
- **HTTP Client**: Axios

## API Endpoints

### 1. Analyze Wallet
```
POST /api/wallet/analyze
Content-Type: application/json

Request Body:
{
  "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
}

Response:
{
  "id": "uuid",
  "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
  "totalEthSent": 60517.995001,
  "totalEthReceived": 64874.29838,
  "totalGasFees": 2.570185,
  "netEth": 4353.733195,
  "outgoingTransactionCount": 1000,
  "incomingTransactionCount": 1000,
  "tokensSent": { ... },
  "tokensReceived": { ... },
  "recentTransactions": [ ... ],
  "timestamp": "2025-11-10T23:01:08.848029Z"
}
```

### 2. Get Analysis History
```
GET /api/wallet/history?limit=10

Response: Array of WalletAnalysisResponse objects
```

## Configuration

### Environment Variables

**Backend (.env)**
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
ALCHEMY_API_KEY="U2_F7nkCGFY73wbiIFpum"
```

**Frontend (.env)**
```
REACT_APP_BACKEND_URL=https://cryptotracker-63.preview.emergentagent.com
```

## How It Works

### Transaction Fetching
1. Uses Alchemy's `alchemy_getAssetTransfers` API method
2. Fetches both outgoing (fromAddress) and incoming (toAddress) transfers
3. Includes categories: external, internal, erc20, erc721, erc1155
4. Maximum 1000 transactions per direction

### Gas Fee Calculation
1. Fetches transaction receipts using `eth_getTransactionReceipt`
2. Calculates: `gasUsed × effectiveGasPrice`
3. Converts from Wei to ETH (divide by 10^18)
4. Limited to 100 transactions for performance

### Error Handling
- Address format validation (must be 0x... and 42 characters)
- API error handling (503, timeouts, invalid responses)
- None value handling in transaction data
- User-friendly error messages in UI

## Testing

### Test Wallet Addresses
1. **Vitalik's Address** (tested, working): `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045`
   - Results: ~60K ETH sent, ~64K ETH received, ~2.57 ETH gas fees
   - Net: +4,353 ETH profit

2. **Note**: Contract addresses (like USDC) may hit rate limits

## UI Screenshots

### Main Interface
- Clean input form with wallet address field
- Purple "Analyze" button with loading state
- Error alerts in red

### Analysis Dashboard
- 4 Summary cards showing key metrics
- Wallet information section
- ERC-20 token activity (split into sent/received)
- Recent transactions table with:
  - Type badges (Sent/Received)
  - Clickable transaction hashes
  - Asset symbols
  - Amounts
  - Addresses

## Blockchain Coverage

### Supported Networks
- **Ethereum Mainnet** (current implementation)

### Token Support
- **Native ETH**: Full support
- **ERC-20 Tokens**: Full support (covers most top 100 cryptos)
  - USDT, USDC, DAI, LINK, UNI, MKR, etc.
- **ERC-721**: Detected but not calculated
- **ERC-1155**: Detected but not calculated

### Top 100 Crypto Coverage
Most top 100 cryptocurrencies exist as ERC-20 tokens on Ethereum:
- Stablecoins: USDT, USDC, DAI
- DeFi: UNI, LINK, MKR, AAVE, COMP
- Exchange tokens: Many centralized exchange tokens
- Meme coins: Various tokens

## Future Enhancements

### Potential Improvements
1. **Multi-chain support**
   - Bitcoin (BTC)
   - Binance Smart Chain (BSC)
   - Solana (SOL)
   - Polygon (MATIC)

2. **USD Values**
   - Historical price data
   - Calculate USD values for transactions
   - Profit/loss in fiat currency

3. **Advanced Analytics**
   - Charts and graphs (transaction volume over time)
   - Top tokens by value
   - Gas fee trends
   - Wallet activity timeline

4. **Export Features**
   - Export to CSV
   - Generate PDF reports
   - Tax calculation assistance

5. **Wallet Management**
   - Save multiple wallets
   - Compare wallets
   - Portfolio tracking

6. **Real-time Updates**
   - WebSocket integration
   - Auto-refresh for new transactions
   - Price alerts

## Known Limitations

1. **Transaction Limit**: Maximum 1000 transactions per direction (Alchemy API limit)
2. **Gas Fee Calculation**: Limited to 100 most recent transactions for performance
3. **Rate Limits**: Alchemy free tier has rate limits
4. **Contract Addresses**: Very active contracts may timeout or hit rate limits
5. **Blockchain Coverage**: Currently Ethereum only

## Performance Notes

- Average analysis time: 5-15 seconds for active wallets
- Depends on:
  - Number of transactions
  - Alchemy API response time
  - Network latency
  
## Security Considerations

- API key stored in environment variable (not exposed to frontend)
- Address validation before API calls
- CORS configured for security
- No private key handling (read-only access)
- Public blockchain data only

## Maintenance

### Updating Alchemy API Key
1. Edit `/app/backend/.env`
2. Update `ALCHEMY_API_KEY` value
3. Restart backend: `sudo supervisorctl restart backend`

### Database Management
```bash
# View stored analyses
mongosh
use test_database
db.wallet_analyses.find().pretty()
```

## Support

For issues or questions:
1. Check backend logs: `tail -f /var/log/supervisor/backend.*.log`
2. Check frontend logs: `tail -f /var/log/supervisor/frontend.*.log`
3. Verify Alchemy API key is valid
4. Test with known working address (Vitalik's address)
