const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
const digitPattern = /[0-9]/g;
const localizedAttributes = ["aria-label", "placeholder", "title", "alt"] as const;

function toPersianDigits(value: string): string {
  return value.replace(digitPattern, (digit) => persianDigits[Number(digit)]);
}

function localizeNode(node: Node): void {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.nodeValue;
    if (text && digitPattern.test(text)) {
      digitPattern.lastIndex = 0;
      node.nodeValue = toPersianDigits(text);
    }
    digitPattern.lastIndex = 0;
    return;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return;
  const element = node as Element;
  if (element.tagName === "SCRIPT" || element.tagName === "STYLE" || element.tagName === "TEXTAREA") return;

  for (const attribute of localizedAttributes) {
    const value = element.getAttribute(attribute);
    if (value && digitPattern.test(value)) element.setAttribute(attribute, toPersianDigits(value));
    digitPattern.lastIndex = 0;
  }

  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
  let current: Node | null;
  while ((current = walker.nextNode())) localizeNode(current);
}

export function observePersianDigits(root: HTMLElement): () => void {
  localizeNode(root);
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") {
        localizeNode(record.target);
      } else if (record.type === "attributes") {
        localizeNode(record.target);
      } else {
        record.addedNodes.forEach(localizeNode);
      }
    }
  });
  observer.observe(root, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [...localizedAttributes],
  });
  return () => observer.disconnect();
}
