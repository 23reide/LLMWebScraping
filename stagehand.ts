import { localBrowser, Stagehand } from "@browserbasehq/stagehand";
import { z } from "zod/v4";

// Cookies persist in ./browser-data, so the next run starts already signed in
const browser = await localBrowser.launch({ headless: true });
const stagehand = await Stagehand.create({
  browser,
  model: {
    generate: async (params) => {
      if (params.responseFormat?.type !== "json_schema") {
        throw new TypeError("Stagehand requested an unsupported Ollama response format");
      }

      const messages: Array<{
        role: "system" | "assistant" | "user";
        content: string;
        images?: string[];
      }> = params.messages.map((message) => {
        const blocks = Array.isArray(message.content) ? message.content : [message.content];
        const text = blocks
          .filter((block) => block.type === "text")
          .map((block) => block.text)
          .join("\n");
        const images = blocks
          .filter((block) => block.type === "image")
          .map((block) => block.data);

        return { role: message.role, content: text, ...(images.length > 0 ? { images } : {}) };
      });

      if (params.systemPrompt) {
        messages.unshift({ role: "system", content: params.systemPrompt });
      }

      const response = await fetch(
        `${process.env.OLLAMA_URL ?? "http://localhost:11434"}/api/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: process.env.OLLAMA_MODEL ?? "llama3.2",
            messages,
            format: params.responseFormat.schema,
            stream: false,
            options:
              params.temperature === undefined
                ? undefined
                : { temperature: params.temperature },
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`Ollama request failed (${response.status}): ${await response.text()}`);
      }

      const result: { message?: { content?: string } } = await response.json();
      const text = result.message?.content;
      if (text === undefined) {
        throw new Error("Ollama returned a response without message content");
      }

      return {
        role: "assistant",
        content: { type: "text", text },
        outputFormat: "json_schema",
        structuredContent: JSON.parse(text),
      };
    },
  },
});

const [page] = await browser.context.pages();
await page.goto("https://app.example.com/login");

// observe() returns real selectors, so credentials never reach the model
const { data: email } = await stagehand.observe("find the email input");
const { data: password } = await stagehand.observe("find the password input");
await page.locator(email[0].selector).fill(process.env.APP_EMAIL!);
await page.locator(password[0].selector).fill(process.env.APP_PASSWORD!);

// act() self-heals when the site redesigns its form
await stagehand.act("click the sign in button");
await stagehand.act("open the billing page");

// extract() returns schema-validated data
const { data } = await stagehand.extract(
  "extract every invoice in the table",
  z.object({
    invoices: z.array(z.object({ number: z.string(), amount: z.number(), paid: z.boolean() })),
  }),
);

console.log(data.invoices);

await stagehand.close();
await browser.close();