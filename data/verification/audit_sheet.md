# Human audit sheet — 15-app stratified sample

You are checking the agent's FIRST-PASS answers (what it said before verification).
For each app: open the evidence links, check the answer against the real docs, mark right/wrong/unsure.
Fill the HTML form (audit.html) and click 'Generate results JSON', save as data/verification/audit_results.json — or edit the marks below.

## 1. Salesforce (CRM and Sales)
What it does: Salesforce is a CRM and sales management platform providing enterprise cloud solutions.
- Auth method(s): **['oauth2', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://developer.salesforce.com/docs/platform/api-rest/guide/quickstart-oauth.html

## 3. Pipedrive (CRM and Sales)
What it does: Pipedrive is a sales pipeline CRM designed to help businesses track sales activities, manage leads and deals, and automate sales processes.
- Auth method(s): **['api key', 'oauth2']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://www.pipedrive.com/ | https://developers.pipedrive.com/docs/api/v1 | https://developers.pipedrive.com/docs/api/v1/Oauth | https://pipedrive.readme.io/docs/core-api-concepts-authentication

## 4. Attio (CRM and Sales)
What it does: Attio is a customizable CRM platform for managing pipelines, deals, customer relationships, and AI agent workflows.
- Auth method(s): **['api key', 'basic', 'oauth2', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://attio.com/ | https://docs.attio.com/rest-api/guides/authentication | https://docs.attio.com/rest-api/overview | https://docs.attio.com/mcp/overview

## 7. Zoho CRM (CRM and Sales)
What it does: Zoho CRM is a sales CRM platform featuring AI assistance, workflow automation, customer engagement, and forecasting tools.
- Auth method(s): **['other: unknown']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **unknown**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://www.zoho.com/en-in/crm/

## 20. Gladly (Support and Helpdesk)
What it does: Gladly is a customer service platform that provides APIs for managing customer profiles, conversations, and support interactions.
- Auth method(s): **['basic']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **admin_approval**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://developer.gladly.com/rest/ | https://help.gladly.com/docs/what-are-mcp-connections

## 26. Discord (Communications and Messaging)
What it does: A communication platform providing an API for bots and applications to interact with servers, channels, and users.
- Auth method(s): **['basic', 'oauth2', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **community**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://docs.discord.com/developers/topics/oauth2 | https://docs.discord.com/developers/reference | https://github.com/jonvanausdeln/discord-mcp

## 27. Telegram (Communications and Messaging)
What it does: Telegram is a cloud-based mobile and desktop messaging app with a focus on security and speed.
- Auth method(s): **['other: api id and hash']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **other: MTProto / HTTP**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **community**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://github.com/sparfenyuk/mcp-telegram | https://core.telegram.org/gateway/api | https://core.telegram.org/api/auth

## 40. SendGrid (Marketing, Ads, Email and Social)
What it does: A cloud-based email delivery service that provides APIs for sending emails, managing templates, and tracking email statistics.
- Auth method(s): **['api key', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **community**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://www.twilio.com/docs/sendgrid/for-developers/sending-email/authentication | https://github.com/recepyavuz0/sendgrid-mcp-server

## 41. Shopify (Ecommerce)
What it does: An ecommerce platform providing APIs for store management, app development, billing, and developer tooling.
- Auth method(s): **['oauth2']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **GraphQL**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://shopify.dev/changelog/posts/mcp-server-for-the-shopify-dev-assistant | https://shopify.dev/docs/api/ai-toolkit | https://shopify.dev/docs/apps/launch/billing/shopify-app-pricing

## 42. WooCommerce (Ecommerce)
What it does: An e-commerce platform for WordPress that provides REST APIs and MCP support for managing products, orders, and store operations.
- Auth method(s): **['api key', 'basic', 'other: application password']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://developer.woocommerce.com/docs/features/mcp | https://woocommerce.com/document/woocommerce-rest-api/

## 54. MrScraper (Data, SEO and Scraping)
What it does: MrScraper is an API for programmatic web scraping, allowing users to extract HTML, Markdown, screenshots, brand data, and structured JSON from web pages, and perform web searches.
- Auth method(s): **['api key', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **paid_plan**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://docs.mrscraper.com/docs/api/overview | https://docs.mrscraper.com/docs/getting-started/scraper-api | https://docs.mrscraper.com/docs/api/authentication | https://docs.mrscraper.com/docs/getting-started/api-token

## 66. Neo4j (Developer, Infra and Data platforms)
What it does: Neo4j is a graph database management system that allows for storing, querying, and managing highly connected data using the Cypher query language.
- Auth method(s): **['basic', 'token']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://neo4j.com/docs/http-api/current/ | https://neo4j.com/docs/mcp/current/

## 74. Jira (Productivity and Project Management)
What it does: Jira is a cloud‑based project management and issue tracking platform.
- Auth method(s): **['basic', 'oauth2']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/ | https://github.com/atlassian/atlassian-mcp-server

## 81. Stripe (Finance and Fintech)
What it does: Stripe provides a comprehensive payment and financial services API for accepting payments, managing subscriptions, and handling payouts.
- Auth method(s): **['api key']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **free_self_serve**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **none**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://docs.stripe.com/api/authentication | https://docs.stripe.com/api | https://docs.stripe.com/apis

## 92. Otter AI (AI, Research and Media-native)
What it does: AI-powered meeting transcription, summarization, and action‑item extraction for teams
- Auth method(s): **['api key', 'oauth2']**  → [ ] right  [ ] wrong  [ ] unsure
- Self-serve vs gated: **partner_gated**  → [ ] right  [ ] wrong  [ ] unsure
- API type: **REST**  → [ ] right  [ ] wrong  [ ] unsure
- Existing MCP: **official**  → [ ] right  [ ] wrong  [ ] unsure
- Buildability: **ready**  → [ ] right  [ ] wrong  [ ] unsure
- Evidence: https://help.otter.ai/hc/en-us/articles/36130822688279-Otter-ai-Public-API | https://help.otter.ai/hc/en-us/articles/35287607569687-Otter-MCP-Server
