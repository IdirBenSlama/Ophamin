/**
 * JSON parser that preserves the int-vs-float distinction.
 *
 * Standard JS ``JSON.parse`` parses both ``42`` and ``42.0`` to the
 * same JavaScript number, losing the type information Python emits
 * in its canonical form. For byte-equivalent re-canonicalization on
 * the JS side, we must know whether a numeric literal in the source
 * carried a decimal point / exponent.
 *
 * This parser walks the text directly and wraps integers in
 * :class:`PyInt`. Strings, booleans, null, arrays, and objects work
 * exactly like ``JSON.parse``.
 *
 * The implementation is a textbook recursive-descent parser. It is
 * NOT a JSON-permissive parser — only standard JSON is accepted
 * (no comments, no trailing commas, no NaN/Infinity at the lexical
 * layer). NaN/Infinity in the source would also break the canonical-
 * form invariants and are rejected loud by the encoder anyway.
 */

import { CanonicalValue, PyInt } from "./canonical.js";

// PyInt is exported from canonical.ts to keep the value-type
// definitions co-located. Re-export here for ergonomic imports.
export { PyInt } from "./canonical.js";

export class JsonParseError extends Error {
  constructor(message: string, public readonly pos: number) {
    super(`JSON parse error at position ${pos}: ${message}`);
    this.name = "JsonParseError";
  }
}

class Parser {
  pos = 0;

  constructor(public readonly text: string) {}

  parse(): CanonicalValue {
    this.skipWhitespace();
    const result = this.parseValue();
    this.skipWhitespace();
    if (this.pos !== this.text.length) {
      throw new JsonParseError(
        `unexpected trailing content`,
        this.pos,
      );
    }
    return result;
  }

  private skipWhitespace(): void {
    while (this.pos < this.text.length) {
      const c = this.text.charCodeAt(this.pos);
      // Spec whitespace: 0x09 (tab), 0x0a (LF), 0x0d (CR), 0x20 (space)
      if (c === 0x09 || c === 0x0a || c === 0x0d || c === 0x20) {
        this.pos++;
      } else {
        break;
      }
    }
  }

  private parseValue(): CanonicalValue {
    this.skipWhitespace();
    if (this.pos >= this.text.length) {
      throw new JsonParseError("unexpected end of input", this.pos);
    }
    const c = this.text[this.pos]!;
    if (c === "{") return this.parseObject();
    if (c === "[") return this.parseArray();
    if (c === '"') return this.parseString();
    if (c === "t" || c === "f") return this.parseBool();
    if (c === "n") return this.parseNull();
    if (c === "-" || (c >= "0" && c <= "9")) return this.parseNumber();
    throw new JsonParseError(
      `unexpected character ${JSON.stringify(c)}`,
      this.pos,
    );
  }

  private parseObject(): { [key: string]: CanonicalValue } {
    this.expect("{");
    this.skipWhitespace();
    const obj: { [key: string]: CanonicalValue } = {};
    if (this.peek() === "}") {
      this.pos++;
      return obj;
    }
    while (true) {
      this.skipWhitespace();
      const key = this.parseString();
      this.skipWhitespace();
      this.expect(":");
      const value = this.parseValue();
      obj[key] = value;
      this.skipWhitespace();
      const next = this.peek();
      if (next === ",") {
        this.pos++;
      } else if (next === "}") {
        this.pos++;
        return obj;
      } else {
        throw new JsonParseError(
          `expected ',' or '}' in object`,
          this.pos,
        );
      }
    }
  }

  private parseArray(): CanonicalValue[] {
    this.expect("[");
    this.skipWhitespace();
    const arr: CanonicalValue[] = [];
    if (this.peek() === "]") {
      this.pos++;
      return arr;
    }
    while (true) {
      arr.push(this.parseValue());
      this.skipWhitespace();
      const next = this.peek();
      if (next === ",") {
        this.pos++;
      } else if (next === "]") {
        this.pos++;
        return arr;
      } else {
        throw new JsonParseError(
          `expected ',' or ']' in array`,
          this.pos,
        );
      }
    }
  }

  private parseString(): string {
    this.expect('"');
    let out = "";
    while (this.pos < this.text.length) {
      const c = this.text[this.pos]!;
      if (c === '"') {
        this.pos++;
        return out;
      }
      if (c === "\\") {
        this.pos++;
        if (this.pos >= this.text.length) {
          throw new JsonParseError(
            "unterminated escape sequence",
            this.pos,
          );
        }
        const esc = this.text[this.pos]!;
        this.pos++;
        if (esc === '"') out += '"';
        else if (esc === "\\") out += "\\";
        else if (esc === "/") out += "/";
        else if (esc === "b") out += "\b";
        else if (esc === "f") out += "\f";
        else if (esc === "n") out += "\n";
        else if (esc === "r") out += "\r";
        else if (esc === "t") out += "\t";
        else if (esc === "u") {
          if (this.pos + 4 > this.text.length) {
            throw new JsonParseError(
              "incomplete \\u escape",
              this.pos,
            );
          }
          const hex = this.text.slice(this.pos, this.pos + 4);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
            throw new JsonParseError(
              `bad \\u escape: ${hex}`,
              this.pos,
            );
          }
          this.pos += 4;
          out += String.fromCharCode(parseInt(hex, 16));
        } else {
          throw new JsonParseError(
            `unknown escape sequence \\${esc}`,
            this.pos - 1,
          );
        }
      } else {
        out += c;
        this.pos++;
      }
    }
    throw new JsonParseError("unterminated string", this.pos);
  }

  private parseBool(): boolean {
    if (this.text.startsWith("true", this.pos)) {
      this.pos += 4;
      return true;
    }
    if (this.text.startsWith("false", this.pos)) {
      this.pos += 5;
      return false;
    }
    throw new JsonParseError("expected 'true' or 'false'", this.pos);
  }

  private parseNull(): null {
    if (this.text.startsWith("null", this.pos)) {
      this.pos += 4;
      return null;
    }
    throw new JsonParseError("expected 'null'", this.pos);
  }

  /**
   * Parse a number, distinguishing integers from floats by the
   * presence of a decimal point or exponent.
   */
  private parseNumber(): number | PyInt {
    const start = this.pos;
    let isFloat = false;
    if (this.text[this.pos] === "-") this.pos++;
    while (
      this.pos < this.text.length &&
      this.text[this.pos]! >= "0" &&
      this.text[this.pos]! <= "9"
    ) {
      this.pos++;
    }
    if (this.text[this.pos] === ".") {
      isFloat = true;
      this.pos++;
      while (
        this.pos < this.text.length &&
        this.text[this.pos]! >= "0" &&
        this.text[this.pos]! <= "9"
      ) {
        this.pos++;
      }
    }
    if (this.text[this.pos] === "e" || this.text[this.pos] === "E") {
      isFloat = true;
      this.pos++;
      if (
        this.text[this.pos] === "+" ||
        this.text[this.pos] === "-"
      ) {
        this.pos++;
      }
      while (
        this.pos < this.text.length &&
        this.text[this.pos]! >= "0" &&
        this.text[this.pos]! <= "9"
      ) {
        this.pos++;
      }
    }
    const raw = this.text.slice(start, this.pos);
    const value = Number(raw);
    if (Number.isNaN(value)) {
      throw new JsonParseError(`invalid number ${raw}`, start);
    }
    if (isFloat) {
      return value;
    }
    if (!Number.isInteger(value) || !Number.isSafeInteger(value)) {
      // A literal without decimal point that exceeds JS's safe-integer
      // range. We do NOT support BigInt here because Python's int is
      // unbounded; in practice Ophamin records do not emit such
      // values, but we surface them rather than silently rounding.
      throw new JsonParseError(
        `integer literal ${raw} exceeds JS safe-integer range; ` +
          `the JS read API does not support arbitrary-precision ints`,
        start,
      );
    }
    return new PyInt(value);
  }

  private expect(ch: string): void {
    if (this.text[this.pos] !== ch) {
      throw new JsonParseError(
        `expected ${JSON.stringify(ch)}`,
        this.pos,
      );
    }
    this.pos++;
  }

  private peek(): string | undefined {
    return this.text[this.pos];
  }
}

/** Parse a JSON text preserving Python's int-vs-float distinction. */
export function parseJsonPreservingInts(text: string): CanonicalValue {
  return new Parser(text).parse();
}
