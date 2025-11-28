# Agensium V2 Architecture: A Beginner's Guide

This guide explains the technical changes proposed for Agensium V2 using simple, real-world analogies. We are moving from a "Personal Project" setup to a "Professional Enterprise" setup.

---

## 1. The Core Problem: "The One-Person Coffee Shop"

**Current Situation (Synchronous):**
Imagine a coffee shop with only **one employee**.

1.  A customer orders a complex latte.
2.  The employee stops taking orders.
3.  The employee goes to the machine, steams milk, pulls the shot, and makes the drink.
4.  Only _after_ the drink is done does the employee go back to the register to take the next order.

**The Result:** If the latte takes 5 minutes, the line goes out the door. Everyone waits.

**The Solution (Asynchronous):**
We want a **Cashier** (API) and a **Barista** (Worker).

1.  Customer orders.
2.  Cashier writes it on a ticket, hands it to the Barista, and immediately says "Next please!" to the next customer.
3.  The Barista makes the drink in the background.

---

## 2. The Database: SQLite vs. MySQL

### The Analogy: "Personal Diary vs. Shared Google Doc"

- **Currently (SQLite):**

  - Think of SQLite as a **physical paper notebook**.
  - It's great for one person. You can write in it easily.
  - **The Problem:** If two people try to write in the same notebook at the same time, they bump elbows. One has to wait for the other to finish. In a web app, this causes errors when multiple users try to save data simultaneously.

- **The Upgrade (MySQL):**
  - Think of MySQL as a **Google Sheet** or a robust filing system.
  - Hundreds of people can edit different rows at the exact same time without blocking each other.
  - **Why we need it:** As you get more users, you need a database that can handle many people reading and writing data at once.

---

## 3. The "Async" System: Celery & Redis

### The Analogy: "The Kitchen Ticket Rail"

To make the "Cashier + Barista" system work, you need a way for them to communicate.

1.  **The API (FastAPI):** This is the **Cashier**. Their only job is to say "I received your file, here is your ticket number (Task ID)." They are very fast.
2.  **Redis:** This is the **Ticket Rail** in the kitchen. The Cashier sticks the order ticket here. It holds the list of work to be done.
3.  **Celery:** These are the **Chefs/Baristas**. They stand in the kitchen, watch the Ticket Rail (Redis), pick up the next ticket, and do the hard work (processing the data).

**Why this is better:**

- You can add more Chefs (Celery Workers) if the restaurant gets busy, without changing the Cashier.
- If a Chef drops a plate (error), the Cashier is still working fine.

---

## 4. File Storage: S3 / Blob Storage

### The Analogy: "Backpack vs. Warehouse"

- **Currently:**

  - When a user uploads a file, the server tries to hold it in its "hands" (RAM/Memory) while working on it.
  - **The Problem:** If 10 people hand the server heavy boxes (large files), the server drops everything and collapses (runs out of RAM).

- **The Upgrade (S3):**
  - Think of S3 as a massive, infinite **Warehouse** with shelves.
  - When a file arrives, we immediately put it on a shelf in the Warehouse.
  - We just give the Chef a slip of paper saying "The ingredients are on Shelf B-12."
  - The Chef goes to the shelf, gets only what they need, and cooks.
  - **Benefit:** The server never gets tired holding heavy files.

---

## 5. Deployment: Docker

### The Analogy: "Recipe vs. Meal Kit"

- **Currently:**

  - To run your code on a new computer, you have to manually install Python, install libraries, set up folders, etc. It's like following a recipe where you have to go to 5 different grocery stores to find ingredients. Sometimes the store is out of stock (version conflicts).

- **The Upgrade (Docker):**
  - Docker is like a **HelloFresh Meal Kit**.
  - It puts your code, the database settings, the libraries, and the operating system into a sealed box.
  - You can hand this box to _any_ computer, and it will run exactly the same way. You don't need to install anything on the computer except the "Box Opener" (Docker).

---

## Summary of the New Flow

1.  **User** uploads a file.
2.  **API (Cashier)** saves the file to the **Warehouse (S3)**.
3.  **API** puts a ticket on the **Rail (Redis)** and gives the User a receipt ("Check back later!").
4.  **Worker (Chef)** sees the ticket, grabs the file from the **Warehouse**, and processes it.
5.  **Worker** saves the results to the **Google Sheet (MySQL)**.
6.  **User** checks their receipt, sees the work is done, and downloads the result.
