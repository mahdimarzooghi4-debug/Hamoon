const persianDigits = "۰۱۲۳۴۵۶۷۸۹";
const digitPattern = /[0-9]/g;
const localizedAttributes = [
  "aria-label",
  "aria-valuetext",
  "aria-description",
  "placeholder",
  "title",
  "alt",
] as const;

function toPersianDigits(value: string): string {
  return value.replace(digitPattern, (digit) => persianDigits[Number(digit)]);
}

function localizeTextNode(node: Node): void {
  const text = node.nodeValue;
  if (text && /[0-9]/.test(text)) node.nodeValue = toPersianDigits(text);
}

function localizeElement(element: Element): void {
  if (element.tagName === "SCRIPT" || element.tagName === "STYLE" || element.tagName === "TEXTAREA") return;
  for (const attribute of localizedAttributes) {
    const value = element.getAttribute(attribute);
    if (value && /[0-9]/.test(value)) element.setAttribute(attribute, toPersianDigits(value));
  }
}

function localizeNode(node: Node): void {
  if (node.nodeType === Node.TEXT_NODE) {
    localizeTextNode(node);
    return;
  }

  if (node.nodeType !== Node.ELEMENT_NODE) return;
  const element = node as Element;
  localizeElement(element);
  if (element.tagName === "SCRIPT" || element.tagName === "STYLE" || element.tagName === "TEXTAREA") return;

  const walker = document.createTreeWalker(element, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  let current: Node | null;
  while ((current = walker.nextNode())) {
    if (current.nodeType === Node.TEXT_NODE) localizeTextNode(current);
    else localizeElement(current as Element);
  }
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
