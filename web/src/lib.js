// Browser bundle entry: the pieces of genlayer-js the Circuit UI needs.
import { createClient, abi } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
export { createClient, studioDevnet };
export const calldata = abi.calldata;
