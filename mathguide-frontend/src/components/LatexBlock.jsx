import { useMemo } from 'react';
import katex from 'katex';

function renderLatex(text, displayMode) {
  try {
    return katex.renderToString(text, {
      displayMode,
      throwOnError: false,
      strict: false,
      maxSize: 500,
    });
  } catch {
    return escapeHtml(text);
  }
}

// O(n) manual parser — no regex, no backtracking
function parseMixedContent(content) {
  if (!content) return [];
  const parts = [];
  let i = 0;
  const len = content.length;

  while (i < len) {
    if (content[i] === '*' && i + 1 < len && content[i + 1] === '*') {
      // Bold **...** — may contain math inside
      const end = content.indexOf('**', i + 2);
      if (end !== -1) {
        const inner = content.slice(i + 2, end);
        parts.push({ type: 'bold', children: parseMixedContent(inner) });
        i = end + 2;
      } else {
        parts.push({ type: 'text', text: content[i] });
        i++;
      }
    } else if (content[i] === '\\' && i + 2 < len && content[i + 1] === '(') {
      // Inline math \(...\)
      const end = content.indexOf('\\)', i + 2);
      if (end !== -1) {
        const latex = content.slice(i + 2, end).trim();
        parts.push({ type: 'inline', text: latex });
        i = end + 2;
      } else {
        parts.push({ type: 'text', text: content[i] });
        i++;
      }
    } else if (content[i] === '\\' && i + 2 < len && content[i + 1] === '[') {
      // Display math \[...\]
      const end = content.indexOf('\\]', i + 2);
      if (end !== -1) {
        const latex = content.slice(i + 2, end).trim();
        parts.push({ type: 'display', text: latex });
        i = end + 2;
      } else {
        parts.push({ type: 'text', text: content[i] });
        i++;
      }
    } else if (content[i] === '$' && i + 1 < len && content[i + 1] === '$') {
      // Display math $$...$$
      const end = content.indexOf('$$', i + 2);
      if (end !== -1) {
        const latex = content.slice(i + 2, end).trim();
        parts.push({ type: 'display', text: latex });
        i = end + 2;
      } else {
        // Unclosed $$, treat as text
        parts.push({ type: 'text', text: content[i] });
        i++;
      }
    } else if (content[i] === '$') {
      // Inline math $...$
      const end = content.indexOf('$', i + 1);
      if (end !== -1 && !content.slice(i + 1, end).includes('\n')) {
        const latex = content.slice(i + 1, end).trim();
        parts.push({ type: 'inline', text: latex });
        i = end + 1;
      } else {
        // No closing $ or multiline, treat as text
        parts.push({ type: 'text', text: content[i] });
        i++;
      }
    } else {
      // Regular text — accumulate until next delimiter
      const nextDollar = content.indexOf('$', i);
      const nextParen = content.indexOf('\\(', i);
      const nextBracket = content.indexOf('\\[', i);
      const nextBold = content.indexOf('**', i);
      let textEnd = len;
      if (nextDollar !== -1 && nextDollar < textEnd) textEnd = nextDollar;
      if (nextParen !== -1 && nextParen < textEnd) textEnd = nextParen;
      if (nextBracket !== -1 && nextBracket < textEnd) textEnd = nextBracket;
      if (nextBold !== -1 && nextBold < textEnd) textEnd = nextBold;
      // Guard against infinite loop when delimiter starts at i
      if (textEnd <= i) textEnd = i + 1;
      parts.push({ type: 'text', text: content.slice(i, textEnd) });
      i = textEnd;
    }
  }
  return parts;
}

// Convert text with Markdown formatting to HTML, keeping user text safe
function processText(text) {
  // 1. Escape & first (must be before any other escaping)
  let out = text.replace(/&/g, '&amp;');

  // 2. Markdown headings (must be at line start)
  out = out.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  out = out.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  out = out.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // 3. Protect our HTML tags before escaping user < >
  const tagPattern = /<\/?(?:h[123]|strong)>/g;
  const savedTags = [];
  out = out.replace(tagPattern, (match) => {
    const id = savedTags.length;
    savedTags.push(match);
    return `\x00TAG${id}\x00`;
  });

  // 5. Escape user < > "
  out = out.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  // 6. Restore protected tags
  out = out.replace(/\x00TAG(\d+)\x00/g, (_, id) => savedTags[parseInt(id)]);

  // 7. Newlines to <br/>
  out = out.replace(/\n/g, '<br/>');

  return out;
}

export default function LatexBlock({ content }) {
  const html = useMemo(() => {
    const parts = parseMixedContent(content);
    return parts.map((part, idx) => {
      if (part.type === 'text') return processText(part.text);
      if (part.type === 'display') return renderLatex(part.text, true);
      if (part.type === 'inline') return renderLatex(part.text, false);
      if (part.type === 'bold') {
        const inner = part.children.map((child) => {
          if (child.type === 'text') return processText(child.text);
          if (child.type === 'display') return renderLatex(child.text, true);
          if (child.type === 'inline') return renderLatex(child.text, false);
          return '';
        }).join('');
        return `<strong>${inner}</strong>`;
      }
      return '';
    }).join('');
  }, [content]);

  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br/>');
}
