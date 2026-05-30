import { describe, test, expect } from "vitest";
import fs from "fs";
import path from "path";
import en from "../../locales/en/common.json";
import fr from "../../locales/fr/common.json";

function getFiles(dir: string): string[] {
  const subdirs = fs.readdirSync(dir);
  const files = subdirs.map((subdir) => {
    const res = path.resolve(dir, subdir);
    return fs.statSync(res).isDirectory() ? getFiles(res) : res;
  });
  return files.reduce<string[]>((acc, file) => acc.concat(file), []);
}

type LocaleTree = Record<string, unknown>;

function hasKey(localeObj: LocaleTree, ns: string, dottedKey: string): boolean {
  let current: unknown = localeObj[ns];
  if (!current) return false;
  for (const part of dottedKey.split(".")) {
    if (current === null || typeof current !== "object") return false;
    current = (current as Record<string, unknown>)[part];
  }
  return current !== undefined;
}

describe("i18n key validation guard", () => {
  test("assert all used translation keys exist in en and fr common.json", () => {
    const srcDir = path.resolve(__dirname, "../../");
    const componentsDir = path.resolve(srcDir, "components");
    const appDir = path.resolve(srcDir, "app");

    const allFiles = [...getFiles(componentsDir), ...getFiles(appDir)].filter(
      (f) => f.endsWith(".ts") || f.endsWith(".tsx")
    );

    const usedKeys = new Set<string>(); // "ns:dotted.key"

    const nsKeyRegex = /\bt\("([a-z_]+):([a-zA-Z0-9_.]+)"/g;
    const commonKeyRegex = /\bt\("([a-zA-Z0-9_.]+)"/g;

    for (const file of allFiles) {
      // Skip test files
      if (file.includes(".test.") || file.includes("/__tests__/")) continue;

      const content = fs.readFileSync(file, "utf8");

      let match;
      // Match namespace keys e.g. t("sidebar:tabs.deliverables")
      while ((match = nsKeyRegex.exec(content)) !== null) {
        usedKeys.add(`${match[1]}:${match[2]}`);
      }

      // Match default namespace keys e.g. t("common.save")
      while ((match = commonKeyRegex.exec(content)) !== null) {
        usedKeys.add(`common:${match[1]}`);
      }
    }

    const missingEn: string[] = [];
    const missingFr: string[] = [];

    for (const key of usedKeys) {
      const ns = key.slice(0, key.indexOf(":"));
      const dotted = key.slice(key.indexOf(":") + 1);
      if (!hasKey(en as LocaleTree, ns, dotted)) missingEn.push(key);
      if (!hasKey(fr as LocaleTree, ns, dotted)) missingFr.push(key);
    }

    const missingAll = new Set([...missingEn, ...missingFr]);

    if (missingAll.size > 0) {
      console.log("Missing i18n Keys Detected:", Array.from(missingAll));
    }

    expect(missingEn).toEqual([]);
    expect(missingFr).toEqual([]);
  });
});
