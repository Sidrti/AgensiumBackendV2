# Form Response Examples

This file contains structured examples of the data objects logged to the console upon form submission. These payloads are ready for backend API integration using a single unified endpoint.

## 1. ContactToDeployModal

Triggered when a user clicks the primary action button on a marketplace tool modal.

```json
{
  "formType": "contact_request",
  "toolId": "profile-my-data",
  "toolName": "Data Profiler",
  "toolCategory": "analyze",
  "requestStatus": "Ready",
  "pocEmail": "john.doe@enterprise.com",
  "useCase": "Need to process 1M rows daily and identify behavioral drift across 5 segments."
}
```

---

## 2. CustomBuilderPage (Template Path)

Triggered when a user completes the multi-step flow starting from a pre-defined template.

```json
{
  "formType": "custom_build",
  "buildType": "template",
  "templateId": "churn-sentinel",
  "templateName": "Churn Sentinel",
  "vision": "I want to connect this to our primary Snowflake instances and flag accounts with >20% activity drop-off.",
  "contact": {
    "name": "Jane Smith",
    "email": "jane@company.com",
    "org": "Acme Corp"
  }
}
```

---

## 3. CustomBuilderPage (Architect My Own Path)

Triggered when a user completes the 5-step custom architecture flow.

```json
{
  "formType": "custom_build",
  "buildType": "own",
  "templateId": null,
  "templateName": null,
  "vision": "A bespoke agentic swarm that monitors shipping logistics and automatically reroutes orders based on weather alerts.",
  "contact": {
    "name": "Bob Logistics",
    "email": "bob@logistics.com",
    "org": "Global Freight Inc"
  },
  "strategicSpecs": {
    "kpi": "Reduce delivery delays by 15%",
    "stack": "AWS Redshift / MQTT Stream / SAP Integration"
  }
}
```
