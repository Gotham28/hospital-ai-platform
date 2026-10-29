"""Unit tests for sentence-boundary passage chunking."""

import unittest

from backend.research.guard.nli import _decompose_passages


class ChunkingTest(unittest.TestCase):
    def test_short_passage_preserved(self):
        passage = "Dr. Rao is available on Monday from 9:00 AM to 1:00 PM."
        chunks = _decompose_passages([passage])
        self.assertEqual(chunks, [passage])

    def test_sentence_boundary_respected(self):
        s1 = "Dr. Rao is available on Monday and Wednesday."
        s2 = "The consultation fee is 500 rupees."
        s3 = "Please bring all prior medical records to the visit."
        s4 = "Emergency services are available 24/7 at the main hospital building."
        long_passage = " ".join([s1, s2, s3, s4] * 3)
        chunks = _decompose_passages([long_passage])
        for c in chunks:
            # Chunk should not start or end with a partial word
            self.assertTrue(c.endswith("."))
            # Verify abbreviation is not broken
            if "Dr." in c:
                self.assertIn("Dr. Rao", c)

    def test_never_split_mid_sentence(self):
        sentences = [
            "This is sentence number one.",
            "Here is sentence number two with some extra details.",
            "Sentence number three contains additional context about treatments.",
            "Sentence number four describes clinic scheduling policies.",
            "Sentence number five concludes the overview.",
        ]
        text = " ".join(sentences * 4)
        chunks = _decompose_passages([text])
        for chunk in chunks:
            # Every chunk must end with a full sentence ending
            self.assertTrue(chunk.strip().endswith("."))


if __name__ == "__main__":
    unittest.main()
