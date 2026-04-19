import express from 'express';
import { GoogleGenerativeAI } from '@google/generative-ai';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const app = express();
app.use(express.json());
app.use(express.static(__dirname));

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

function extractVideoId(url) {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([^&\n?#]+)/,
    /(?:youtu\.be\/)([^&\n?#]+)/,
    /(?:youtube\.com\/embed\/)([^&\n?#]+)/,
    /(?:youtube\.com\/shorts\/)([^&\n?#]+)/,
  ];
  for (const re of patterns) {
    const m = url.match(re);
    if (m) return m[1];
  }
  return null;
}

app.post('/api/analyze-video', async (req, res) => {
  const { url } = req.body;

  if (!url?.trim()) {
    return res.status(400).json({ error: 'נדרשת כתובת URL של סרטון יוטיוב.' });
  }

  const videoId = extractVideoId(url.trim());
  if (!videoId) {
    return res.status(400).json({ error: 'כתובת ה-URL אינה תקינה. יש להזין קישור יוטיוב תקף.' });
  }

  const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const model = genAI.getGenerativeModel({
    model: 'gemini-2.0-flash-lite',
    systemInstruction:
      'אתה מומחה לזיהוי דיסאינפורמציה ומידע כוזב. צפה בסרטוני יוטיוב והעריך את אמינות תוכנם באופן מדויק ומאוזן. ענה תמיד בעברית.',
  });

  const prompt = `צפה בסרטון היוטיוב הזה ובצע הערכת אמינות מקיפה.

החזר **אך ורק** JSON תקני בפורמט הבא, ללא טקסט נוסף:
{
  "score": <מספר שלם 0-100>,
  "verdict": "<אמין | חלקית נכון | מוטה | כוזב>",
  "verdict_color": "<green | yellow | orange | red>",
  "summary": "<2-3 משפטים על מה הסרטון טוען>",
  "problematic_claims": ["<טענה 1>", "<טענה 2>"],
  "positive_indicators": ["<אינדיקטור 1>"],
  "language_analysis": "<ניתוח סגנון הדיבור: רגש מוגזם, מניפולציה, קליקבייט וכו'>",
  "recommendation": "<המלצה למשתמש מה לעשות עם המידע>"
}`;

  try {
    const result = await model.generateContentStream([
      { fileData: { mimeType: 'video/youtube', fileUri: videoUrl } },
      prompt,
    ]);

    let fullText = '';

    for await (const chunk of result.stream) {
      const delta = chunk.text();
      if (delta) {
        fullText += delta;
        res.write(`data: ${JSON.stringify({ type: 'progress' })}\n\n`);
      }
    }

    const jsonMatch = fullText.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      res.write(`data: ${JSON.stringify({ type: 'error', error: 'שגיאה בפענוח תוצאות הניתוח.' })}\n\n`);
      return res.end();
    }

    const analysis = JSON.parse(jsonMatch[0]);
    res.write(`data: ${JSON.stringify({ type: 'done', analysis, videoId })}\n\n`);
    res.end();
  } catch (err) {
    console.error('Gemini error:', err.message);
    let msg = `שגיאת API: ${err.message || 'שגיאה לא ידועה'}`;
    if (err.message?.includes('API key'))
      msg = 'מפתח ה-API אינו תקין. בדוק את משתנה הסביבה GEMINI_API_KEY.';
    if (err.message?.includes('not supported') || err.message?.includes('not accessible'))
      msg = 'הסרטון אינו נגיש ל-Gemini — ייתכן שהוא פרטי, מוגבל לגיל, או חסום.';
    res.write(`data: ${JSON.stringify({ type: 'error', error: msg })}\n\n`);
    res.end();
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`\n✓ TruthStrike (Gemini) running → http://localhost:${PORT}`);
  if (!process.env.GEMINI_API_KEY) {
    console.warn('⚠  GEMINI_API_KEY is not set.');
  }
});
