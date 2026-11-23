// U8 plan Step 92(j): the complete assembly's shell scenarios in U8's own lane too. They
// also run in U3's and U4's shell lanes (their src/App.tsx floors) and, through all three
// files, in U2's cumulative lane.
import { describeCompleteShell } from './app-shell-scenarios';

describeCompleteShell();
