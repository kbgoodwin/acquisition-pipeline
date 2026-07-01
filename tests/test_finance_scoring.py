import unittest

from acquisition_os.finance import FinancingInputs, model_financing


class FinanceTests(unittest.TestCase):
    def test_model_financing_produces_debt_metrics(self):
        result = model_financing(
            FinancingInputs(
                purchase_price=1_250_000,
                sde=400_000,
                down_payment=125_000,
                interest_rate=0.11,
                term_years=10,
            )
        )

        self.assertEqual(result.sba_loan, 1_125_000)
        self.assertGreater(result.monthly_payment, 0)
        self.assertGreater(result.annual_debt_service, 0)
        self.assertLess(result.post_debt_owner_income, 400_000)
        self.assertGreater(result.maximum_offer, 0)


if __name__ == "__main__":
    unittest.main()
