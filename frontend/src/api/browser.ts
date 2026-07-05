import { setupWorker } from "msw/browser";
import { mockHandlers } from "./mockHandlers";

export const worker = setupWorker(...mockHandlers);
