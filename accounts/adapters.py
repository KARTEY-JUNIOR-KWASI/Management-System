from allauth.account.adapter import DefaultAccountAdapter

class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        """
        Forcefully disable public registration via allauth.
        Only Admins can create accounts via the Admin Dashboard.
        """
        return False
