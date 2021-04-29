from .gpt import GPT, Example
from .models import GPTRequest


class GPT3ParaphraseGenerator:

    """Class creates GPT model for text augmentation"""
    def __init__(self, request_data: GPTRequest):

        self.api_key = request_data.api_key

        self.data = request_data.data
        self.num_responses = request_data.num_responses

        self.gpt = GPT(engine=request_data.engine,
                       temperature=request_data.temperature,
                       max_tokens=request_data.max_tokens)

        self.gpt.add_example(Example('Will I need to irrigate my groundnut field tomorrow?',
                                     'Will my groundnut field need to be watered tomorrow?'))
        self.gpt.add_example(Example('How can I get the vaccine for covid 19?',
                                     'How can I get vaccinated for covid 19?'))

    def paraphrases(self):
        """This function creates prompt using user's input and sends a
        request to gpt3's Completion api for question augmentation

        :param self:
        :return: list of questions"""

        # run loop for each question in data var
        questions_set = set()

        for text in self.data:
            output = self.gpt.submit_request(text, self.num_responses, self.api_key)

            for i in range(self.num_responses):
                questions_set.add(output.choices[i].text.replace('output: ', '').replace('\n', ''))

        return questions_set
